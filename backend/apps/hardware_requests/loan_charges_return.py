"""Loan close: rental charged at return, the late fee (computed once), and release of an
uncollected deposit.

Split out of `loan_payments.py` (still the public barrel). The entry point swallows
payment failures, because a provider outage must never undo a physical return. The late
fee stays per loan, at the highest late rate among the loan's items (A2), computed once
through the pricing kernel and never recomputed.
"""

from django.db import transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.hardware_requests import notifications
from apps.hardware_requests.loan_charges_common import (
    CLOSED_STATUSES,
    _existing,
    _get_or_create,
    _schedule_checkout,
    fee_exempt,
    loans_enabled,
    logger,
)
from apps.hardware_requests.models import HardwareRequest
from apps.payments.models import Payment
from apps.payments.reconciliation import cancel_pending


def on_request_closed(request_id, actor, now=None):
    """Post-commit: rental (at return), the late fee, then release an uncollected deposit."""
    try:
        request = HardwareRequest.objects.select_related("makerspace").get(pk=request_id)
        if request.status not in CLOSED_STATUSES:
            return None
        # Use the recorded return time: delayed post-commit work must not add late
        # days after the borrower has already handed the tool back.
        closed_at = now or request.closed_at or timezone.now()
        _rental_at_return(request, actor, closed_at)
        fee = raise_late_fee(request, actor, closed_at)
        # A deposit nobody paid secures nothing once the loan is over, whether or not a
        # fee was raised -- the fee is its own charge. A PAID deposit stays on the
        # ledger for staff to refund (or keep against the fee) through the refund path.
        cancel_pending(
            makerspace=request.makerspace,
            subject_type=Payment.SubjectType.LOAN_DEPOSIT,
            subject_id=request.pk,
            actor=actor,
        )
        return fee
    except Exception:
        logger.exception("loan_close_payments_failed", extra={"request_id": request_id})
        return None


def _rental_at_return(request, actor, closed_at):
    from apps.hardware_requests.loan_charges_rental import raise_rental

    try:
        return raise_rental(request, actor, at="return", now=closed_at)
    except Exception:
        logger.exception("loan_rental_raise_failed", extra={"request_id": request.pk})
        return None


@transaction.atomic
def raise_late_fee(request, actor, now):
    # Unlike new voluntary obligations, return fees survive an in-flight departure.
    # Serialize the check and debt with Stage A, and keep its extra audit atomic.
    from apps.accounts.models import User
    from apps.makerspaces.models import Makerspace
    from apps.payments.pricing import quote
    from apps.payments.pricing.charging import record_free
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    assert_write_allowed(request.makerspace_id)
    Makerspace.objects.select_for_update().get(pk=request.makerspace_id)
    owner = User.objects.select_for_update(no_key=True).filter(pk=request.requester_id).first()
    if request.return_due_at is None or not loans_enabled(request.makerspace) or fee_exempt(request):
        return None
    existing = _existing(request, Payment.SubjectType.LOAN_LATE_FEE)
    if existing is not None:
        # Computed once at close, never recomputed: a fee that grew after the fact
        # would be a charge the member never saw raised.
        return existing
    priced = quote(request.makerspace, "loans", request, member=request.requester,
                   params={"components": ("late",), "now": now})
    if priced.total <= 0:
        if priced.lines:
            record_free(priced, actor=actor, makerspace=request.makerspace, target=request,
                        subject_type=Payment.SubjectType.LOAN_LATE_FEE, subject_id=request.pk)
        return None
    payment, created = _get_or_create(
        request, Payment.SubjectType.LOAN_LATE_FEE, priced, actor, f"Late return fee - request #{request.pk}",
    )
    if created:
        audit.record(
            actor, "loan.late_fee_raised", makerspace=request.makerspace, target=request,
            meta={"request_id": request.pk, "payment_id": payment.pk},
        )
        if owner is not None and owner.deletion_requested_at is not None:
            audit.record(
                actor, "account.obligation_after_deletion", makerspace=request.makerspace,
                target=owner, meta={"request_id": request.pk, "payment_id": payment.pk,
                                    "subject_type": Payment.SubjectType.LOAN_LATE_FEE},
            )
        notifications.notify_loan_charge(request, "late_fee_raised", payment)
    if payment.status == Payment.Status.PENDING:
        _schedule_checkout(payment)
    return payment
