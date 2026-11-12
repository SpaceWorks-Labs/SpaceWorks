"""Record money returned in person without calling or depending on a provider."""

from django.utils.translation import gettext
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.accounts import rbac
from apps.audit import services as audit
from apps.payments.exceptions_refunds import RefundNotAllowed
from apps.payments.models import Payment, Refund
from apps.payments.serializers_refunds_offline import PaymentOfflineRefundSerializer


def offline_refund_queryset(actor):
    """Manual money-out requires RECORD_PAYMENT, including after rail removal.

    Lane L22 (#137): a subject's own cash authority (`CASH_RECORD_ACTIONS`, the Shop
    Manager for shop orders) also records that subject's cash refunds, and nothing else.
    """
    from apps.payments.reconciliation_authority import CASH_RECORD_ACTIONS

    rows = rbac.scope_by_action(actor, rbac.Action.RECORD_PAYMENT, Payment.objects.all(), field="makerspace_id")
    for subject_type, action in CASH_RECORD_ACTIONS.items():
        rows = rows | rbac.scope_by_action(actor, action, Payment.objects.filter(subject_type=subject_type),
                                           field="makerspace_id")
    return rows


@transaction.atomic
def record_offline_refund(payment, *, amount, reason, receipt, actor, release_deposit=False):
    # Validate here as well as at HTTP: direct service callers must supply a receipt.
    payload = PaymentOfflineRefundSerializer(data={
        "amount": amount, "reason": reason, "receipt": receipt,
    })
    payload.is_valid(raise_exception=True)
    data = payload.validated_data
    locked = (
        offline_refund_queryset(actor).select_for_update(of=("self",)).select_related("makerspace")
        .filter(pk=payment.pk, makerspace_id=payment.makerspace_id).first()
    )
    if locked is None:
        raise NotFound(gettext("Payment not found."))
    if not rbac.can(actor, rbac.Action.RECORD_PAYMENT, locked.makerspace_id):
        # Decision 242(c): an area manager's own cash authority, narrowed by machine type.
        from apps.payments.reconciliation_authority import _require_subject_authority
        _require_subject_authority(actor, [locked])
    if release_deposit:
        from apps.hardware_requests.models import HardwareRequest
        # Audit 0.12.0 C-3: the loan is read in the payment's own space; the actor's authority
        # was decided on the charge above. Scoping it by record_payment refused every area owner
        # (the Inventory Manager releasing a deposit, decision 242(c)) with `deposit_not_returned`.
        closed = HardwareRequest.objects.filter(
            pk=locked.subject_id, makerspace_id=locked.makerspace_id,
            status__in=[HardwareRequest.Status.RETURNED, HardwareRequest.Status.CLOSED_WITH_ISSUE])
        if locked.subject_type != Payment.SubjectType.LOAN_DEPOSIT or not closed.exists():
            raise RefundNotAllowed(gettext("A deposit can be released after the loan closes."), "deposit_not_returned")
    if locked.status != Payment.Status.PAID_OFFLINE:
        raise RefundNotAllowed(gettext("Only offline-settled payments accept a manual refund."), "refund_not_offline")
    from apps.payments.refund_policy import precision_ok
    if not precision_ok(data["amount"], locked.currency):
        # Audit 0.12.0 C-2: no half yen is handed back over a counter.
        raise RefundNotAllowed(gettext("Refund amount is invalid for this currency."), "refund_amount_invalid")
    if Refund.counted_total(locked) + data["amount"] > locked.amount:
        raise RefundNotAllowed(gettext("Refund exceeds the refundable balance."), "refund_exceeds_balance")
    refund = Refund.objects.create(
        payment=locked, amount=data["amount"], currency=locked.currency,
        status=Refund.Status.SUCCEEDED, provider=Refund.Provider.MANUAL,
        reason=data["reason"], created_by=actor, settled_at=timezone.now(),
        **data["receipt"],
    )
    from apps.payments.services_refund_cases import void_exhausted_cases
    void_exhausted_cases(locked, actor=actor)
    audit.record(
        actor, "payment.refund_recorded", makerspace=locked.makerspace, target=locked,
        meta={"payment_id": locked.pk, "refund_id": refund.pk, "amount": str(refund.amount),
              "method": refund.method},
    )
    from apps.payments.notifications import notify_payment
    from apps.payments.documents import issue_credit_note
    issue_credit_note(refund, actor=actor)
    notify_payment(locked, "refund_issued", refund=refund)
    return refund


@transaction.atomic
def amend_offline_refund(payment, *, refund_id, receipt, actor):
    """Correct metadata, not the amount of money actually returned."""
    from apps.payments.serializers_refunds_offline import ManualRefundReceiptSerializer
    payload = ManualRefundReceiptSerializer(data=receipt)
    payload.is_valid(raise_exception=True)
    locked = offline_refund_queryset(actor).select_for_update().filter(
        pk=payment.pk, makerspace_id=payment.makerspace_id,
    ).first()
    if locked is None:
        raise NotFound(gettext("Payment not found."))
    if not rbac.can(actor, rbac.Action.RECORD_PAYMENT, locked.makerspace_id):
        # Audit 0.12.0 C-4: an area owner who recorded a cash refund (242(c)) may correct its
        # receipt, under the same subject authority (machine-type narrowed) that recorded it.
        from apps.payments.reconciliation_authority import _require_subject_authority
        _require_subject_authority(actor, [locked])
    previous = Refund.objects.filter(
        pk=refund_id, payment=locked, provider=Refund.Provider.MANUAL, amended_by__isnull=True,
    ).first()
    if previous is None:
        raise NotFound(gettext("Effective manual refund not found."))
    replacement = Refund.objects.create(
        payment=locked, amount=previous.amount, currency=previous.currency,
        provider=Refund.Provider.MANUAL, status=Refund.Status.SUCCEEDED,
        reason=previous.reason, created_by=actor, settled_at=previous.settled_at,
        amends=previous, **payload.validated_data,
    )
    audit.record(actor, "payment.refund_amended", makerspace=locked.makerspace, target=locked,
                 meta={"payment_id": locked.pk, "refund_id": replacement.pk,
                       "amends_id": previous.pk, "method": replacement.method})
    from apps.payments.documents import issue_credit_note
    issue_credit_note(replacement, actor=actor)
    return replacement
