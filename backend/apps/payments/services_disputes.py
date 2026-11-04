"""Record a provider dispute against its charge. Record-and-flag only (owner decision 71).

Nothing here cancels a booking, ticket or registration, refunds, or touches the Payment
row. A dispute for a charge this deployment never raised is ignored, exactly like an
unknown refund.
"""

from decimal import Decimal

from django.db import transaction

from apps.audit import services as audit
from apps.payments.models_disputes import PaymentDispute, PaymentDisputeEvent
from apps.payments.money import minor_unit_exponent

STRIPE_STATUSES = {
    "warning_needs_response": "open", "needs_response": "open", "warning_under_review": "under_review",
    "under_review": "under_review", "won": "won", "lost": "lost", "warning_closed": "closed",
    "charge_refunded": "closed", "prevented": "closed",
}
RAZORPAY_STATUSES = {
    "open": "open", "created": "open", "action_required": "open", "under_review": "under_review",
    "won": "won", "lost": "lost", "closed": "closed",
}


def normalize(provider, raw):
    table = STRIPE_STATUSES if provider == "stripe" else RAZORPAY_STATUSES
    return table.get(str(raw or "").lower(), "open")


def _amount(minor, currency, payment):
    if not minor:
        return payment.amount
    return Decimal(int(minor)).scaleb(-minor_unit_exponent(currency)).quantize(Decimal("0.01"))


def is_disputed(payment):
    """True while a dispute on the charge is unresolved (shown on tickets and charges)."""
    return PaymentDispute.objects.filter(payment=payment, status__in=("open", "under_review")).exists()


@transaction.atomic
def record_dispute_event(payment, *, provider, dispute_id, raw_status, event_id, minor=0, currency="",
                         reason="", evidence_due_at=None):
    """Create or update the dispute and append its history row. Idempotent per event."""
    status = normalize(provider, raw_status)
    currency = (currency or payment.currency).lower()
    dispute = PaymentDispute.objects.select_for_update().filter(
        provider=provider, provider_dispute_id=dispute_id).first()
    created = dispute is None
    if created:
        dispute = PaymentDispute.objects.create(
            makerspace_id=payment.makerspace_id, payment=payment, provider=provider,
            provider_dispute_id=dispute_id, amount=_amount(minor, currency, payment), currency=currency,
            reason=str(reason or "")[:64], status=status, provider_status=str(raw_status or "")[:32],
            evidence_due_at=evidence_due_at)
    elif dispute.payment_id != payment.pk:
        return None
    if PaymentDisputeEvent.objects.filter(dispute=dispute, provider_event_id=event_id).exists():
        return dispute
    PaymentDisputeEvent.objects.create(dispute=dispute, status=status, provider_status=str(raw_status or "")[:32],
                                       provider_event_id=event_id, amount=_amount(minor, currency, payment))
    if not created and (dispute.status, dispute.provider_status) != (status, str(raw_status or "")[:32]):
        dispute.status, dispute.provider_status = status, str(raw_status or "")[:32]
        dispute.save(update_fields=["status", "provider_status", "updated_at"])
    if not created:
        audit.record(None, "payment.dispute_updated", makerspace=payment.makerspace, target=payment,
                     meta={"dispute_id": dispute.pk, "provider": provider, "status": status, "provider_event": event_id})
    else:
        audit.record(None, "payment.dispute_opened", makerspace=payment.makerspace, target=payment,
                     meta={"dispute_id": dispute.pk, "provider": provider, "status": status, "provider_event": event_id})
        from apps.payments.notifications_l5 import notify_dispute
        transaction.on_commit(lambda: notify_dispute(dispute))
    return dispute
