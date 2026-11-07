"""Receipt rows for offline settlement: the append-only cash-book writes."""

from django.utils.translation import gettext
from django.db import transaction
from rest_framework.exceptions import NotFound

from apps.audit import services as audit
from apps.payments.models import Payment
from apps.payments.reconciliation_authority import _require_record_authority


@transaction.atomic
def amend_settlement(*, actor, makerspace_id, payment_id, settlement):
    """Correct a receipt by APPENDING a replacement, never by editing one.

    The payment itself is already terminal and stays untouched -- this corrects only the
    record of how the money arrived, which is exactly the case the `amends` chain exists
    for: a mistyped reference or the wrong method picked at the desk. Without this the
    field was unreachable and a wrong receipt was permanent, since every reconciliation
    endpoint refuses a terminal payment.
    """
    from apps.payments.models import ManualSettlement

    payment = (
        Payment.objects.select_for_update(of=("self",))
        .select_related("makerspace")
        .filter(makerspace_id=makerspace_id, pk=payment_id)
        .first()
    )
    if payment is None or payment.status != Payment.Status.PAID_OFFLINE:
        raise NotFound(gettext("Settled payment not found."))
    _require_record_authority(actor, [payment])
    current = ManualSettlement.effective_for(payment)
    if current is None:
        raise NotFound(gettext("This payment has no settlement to correct."))
    receipt = ManualSettlement.objects.create(
        payment=payment,
        method=settlement["method"],
        reference=settlement.get("reference", ""),
        received_at=settlement["received_at"],
        amount=payment.amount,
        currency=payment.currency,
        recorded_by=actor,
        amends=current,
    )
    audit.record(
        actor,
        "payment.settlement_amended",
        makerspace=payment.makerspace,
        target=payment,
        meta={
            "settlement_id": receipt.pk,
            "amends_id": current.pk,
            "method": receipt.method,
            "previous_method": current.method,
        },
    )
    from apps.payments.documents import issue_receipt
    issue_receipt(payment, actor=actor, settlement=receipt)
    return receipt


def _record_settlement(payment, actor, settlement):
    """Append the cash-book row for one settled charge.

    Amount and currency are taken from the PAYMENT, never from the caller: the receipt
    describes the debt that was settled, and letting a client name its own figure would
    let the books disagree with the ledger they are supposed to explain.
    """
    from apps.payments.models import ManualSettlement

    return ManualSettlement.objects.create(
        payment=payment,
        method=settlement["method"],
        reference=settlement.get("reference", ""),
        received_at=settlement["received_at"],
        amount=payment.amount,
        currency=payment.currency,
        recorded_by=actor,
    )
