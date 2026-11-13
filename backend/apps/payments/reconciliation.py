"""Transactional reconciliation for every payment subject type."""

from django.utils.translation import gettext
import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from rest_framework.exceptions import APIException, NotFound

from apps.accounts import rbac
from apps.audit import services as audit
from apps.payments.models import Payment
from apps.payments.admission_settlement import resume_admission_after_settlement

# Re-export barrel: these moved to submodules at the 300-line ceiling, but
# `from apps.payments.reconciliation import X` must keep resolving for every caller.
from apps.payments.reconciliation_authority import (  # noqa: F401
    SUBJECT_ACTIONS,
    _require_machine_scope,
    _require_record_authority,
    _require_subject_authority,
    payment_list_action,
)
from apps.payments.reconciliation_rail import _expire_checkout_best_effort  # noqa: F401
from apps.payments.reconciliation_settlement import _record_settlement, amend_settlement  # noqa: F401

logger = logging.getLogger(__name__)


class PaymentConflict(APIException):
    status_code = 409

    def __init__(self, payment_ids):
        self.detail = {
            "detail": "Only pending payments can be reconciled.",
            "code": "payment_terminal",
            "payment_ids": list(payment_ids),
        }


def list_payments(*, actor, makerspace_id, status=None, subject_type=None, for_recording=False, due_state=None):
    # VIEW_FINANCE/RECORD_PAYMENT, or MANAGE_EVENTS for an event-registration listing.
    action = payment_list_action(actor, makerspace_id, for_recording=for_recording, subject_type=subject_type)
    queryset = rbac.scope_by_action(
        actor,
        action,
        Payment.objects.select_related("makerspace"),
        field="makerspace_id",
    ).filter(makerspace_id=makerspace_id)
    if for_recording:
        queryset = queryset.filter(status__in=[Payment.Status.PENDING, Payment.Status.PAID_OFFLINE])
    if status:
        queryset = queryset.filter(status=status)
    if subject_type:
        queryset = queryset.filter(subject_type=subject_type)
    from apps.payments.unit_payer_scope import narrow_payments
    queryset = narrow_payments(queryset, actor, makerspace_id, action)  # parity O-B3: a unit lead's own members
    from apps.makerspaces.models import Makerspace
    from apps.payments.due_dates import filter_due, order_by_due
    makerspace = rbac.scope_by_action(
        actor, action, Makerspace.objects.all(), field="pk",
    ).filter(pk=makerspace_id).first()
    if makerspace is None:
        raise NotFound(gettext("Makerspace not found."))
    return order_by_due(with_refunds(filter_due(queryset, makerspace, due_state)))


def with_refunds(queryset):
    """Annotate the money actually sent back and prefetch the refund lines."""
    from apps.payments.models import Refund

    return queryset.prefetch_related("refunds__amended_by").annotate(
        refunded_amount=Coalesce(
            Sum("refunds__amount", filter=Q(refunds__status=Refund.Status.SUCCEEDED, refunds__amended_by__isnull=True)),
            Value(Decimal("0.00")),
            output_field=DecimalField(max_digits=13, decimal_places=3),
        )
    )


def mark_offline(payment, actor, settlement=None):
    """Settle one charge in cash. `settlement` is REQUIRED -- see reconcile_payments.

    Kept as a one-row convenience over the batch service. Callers that genuinely have no
    receipt detail want `waive` instead: that is the transition meaning "no money moved".
    """
    return _compat_reconcile(
        actor=actor,
        payment=payment,
        target_status=Payment.Status.PAID_OFFLINE,
        settlement=settlement,
    )


def waive(payment, actor):
    return _compat_reconcile(
        actor=actor,
        payment=payment,
        target_status=Payment.Status.WAIVED,
    )


@transaction.atomic
def cancel_pending(*, makerspace, subject_type, subject_id, actor):
    """Cancel a subject's pending charge without affecting its domain workflow."""
    payment = (
        Payment.objects.select_for_update()
        .filter(
            makerspace=makerspace,
            subject_type=subject_type,
            subject_id=subject_id,
        )
        .first()
    )
    if payment is None or payment.status != Payment.Status.PENDING:
        return payment
    _expire_checkout_best_effort(payment)
    payment.status = Payment.Status.CANCELED
    payment.save(
        update_fields=[
            "status",
            "stripe_checkout_session_expired_at",
            "updated_at",
        ]
    )
    audit.record(
        actor,
        "payment.canceled",
        makerspace=makerspace,
        target=payment,
    )
    return payment


def _compat_reconcile(*, payment, actor, target_status, settlement=None):
    current = Payment.objects.get(pk=payment.pk)
    if current.status != Payment.Status.PENDING:
        return current
    return reconcile_payments(
        actor=actor,
        makerspace_id=current.makerspace_id,
        payment_ids=[current.pk],
        target_status=target_status,
        settlement=settlement,
    )[0]


@transaction.atomic
def reconcile_payments(
    *, actor, makerspace_id, payment_ids, target_status, settlement=None
):
    """Lock, validate, then reconcile a batch without partial mutations.

    `settlement` is the manual receipt -- method, reference, received_at -- recorded for
    a PAID_OFFLINE batch. It is written in the same transaction as the status flip, so a
    settled charge can never exist without the cash-book row that explains it. Waiving
    takes no settlement: no money changed hands.
    """
    if target_status not in {Payment.Status.PAID_OFFLINE, Payment.Status.WAIVED}:
        raise ValueError("Unsupported reconciliation status.")
    if settlement and target_status != Payment.Status.PAID_OFFLINE:
        raise ValueError("Only an offline settlement carries receipt details.")
    # Enforced HERE, not only in the HTTP serializers: `mark_offline()` is exported and
    # called directly, so a serializer-only rule would let a settled charge exist with no
    # record of how the money arrived -- exactly what the ledger exists to prevent.
    if target_status == Payment.Status.PAID_OFFLINE and not settlement:
        raise ValueError("Marking a payment paid offline requires settlement details.")

    requested_ids = list(payment_ids)
    locked = list(
        Payment.objects.select_for_update(of=("self",))
        .select_related("makerspace")
        .filter(makerspace_id=makerspace_id, pk__in=requested_ids)
        .order_by("pk")
    )
    by_id = {payment.pk: payment for payment in locked}
    if len(by_id) != len(requested_ids):
        raise NotFound(gettext("Payment not found."))

    from apps.payments.unit_payer_scope import payer_user_ids

    payers = payer_user_ids(actor, makerspace_id, rbac.Action.RECORD_PAYMENT)
    if payers is not None and any(payment.member_id not in payers for payment in locked):
        raise NotFound(gettext("Payment not found."))  # parity O-B3: another unit's charge does not exist for you
    if target_status == Payment.Status.PAID_OFFLINE:
        _require_record_authority(actor, locked)
    else:
        _require_subject_authority(actor, locked)
    terminal_ids = [payment.pk for payment in locked if payment.status != Payment.Status.PENDING]
    if terminal_ids:
        raise PaymentConflict(terminal_ids)

    if target_status == Payment.Status.PAID_OFFLINE:
        from apps.payments.maker_checker import propose, requires_confirmation
        if requires_confirmation(locked[0].makerspace):
            # Maker-checker (lane L5): record the proposal; the charge stays pending
            # until a second person with RECORD_PAYMENT confirms it.
            propose(locked, actor, settlement)
            return [by_id[payment_id] for payment_id in requested_ids]
    for payment in locked:
        apply_reconciliation(payment, actor, target_status, settlement)
    return [by_id[payment_id] for payment_id in requested_ids]


def apply_reconciliation(payment, actor, target_status, settlement=None, *, recorded_by=None):
    """Flip one LOCKED pending charge, writing its receipt in the same transaction."""
    action = "payment.paid_offline" if target_status == Payment.Status.PAID_OFFLINE else "payment.waived"
    _expire_checkout_best_effort(payment)
    payment.status = target_status
    payment.save(update_fields=["status", "stripe_checkout_session_expired_at", "updated_at"])
    meta = None
    receipt = None
    if settlement and target_status == Payment.Status.PAID_OFFLINE:
        receipt = _record_settlement(payment, recorded_by or actor, settlement)
        from apps.payments.documents import issue_receipt
        issue_receipt(payment, actor=actor, settlement=receipt)
        meta = {"method": receipt.method, "settlement_id": receipt.pk}
    audit.record(actor, action, makerspace=payment.makerspace, target=payment, meta=meta)
    from apps.payments.settlement_supersede import supersede_open_settlements
    supersede_open_settlements(payment, actor=actor)
    resume_admission_after_settlement(payment)
    if target_status == Payment.Status.PAID_OFFLINE:
        from apps.payments.notifications import notify_payment
        notify_payment(payment, "payment_received")
    return receipt
