"""Recording one verified online capture against its locked Payment.

Shared by the provider webhooks and the gateway poll (X18), so both paths settle,
flag and receipt identically. Callers hold the Payment row lock inside a transaction
and have already claimed the event id for idempotency.
"""

from apps.audit import services as audit
from apps.payments.admission_settlement import resume_admission_after_settlement
from apps.payments.capture_flags import differs, flag_after_terminal, record_flag
from apps.payments.models import Payment
from apps.payments.models_capture_flags import PaymentCaptureFlag
from apps.payments.notifications import notify_payment


def flags_on(payment):
    from apps.makerspaces.platform import feature_enabled

    return feature_enabled(payment.makerspace, "billing.capture_flags")


def settle_capture(payment, *, provider, capture_id="", event_id="", polled=False, minor=0, currency="",
                   method_label=""):
    """Pending -> paid_online. A capture that differs from the charge is held, not refused."""
    payment.status = Payment.Status.PAID_ONLINE
    fields = ["status", "updated_at"]
    if capture_id and provider == Payment.Provider.STRIPE:
        payment.stripe_payment_intent_id = capture_id
        fields.append("stripe_payment_intent_id")
    elif capture_id:
        payment.external_payment_id = capture_id
        fields.append("external_payment_id")
    if method_label and not payment.method_label:
        payment.method_label = method_label[:64]
        fields.append("method_label")
    payment.save(update_fields=fields)
    if polled:
        audit.record(None, "payment.paid_online", makerspace=payment.makerspace, target=payment,
                     meta={"provider": provider, "event_id": event_id, "polled": True})
    elif provider == Payment.Provider.STRIPE:
        audit.record(None, "payment.paid_online", makerspace=payment.makerspace, target=payment,
                     meta={"stripe_event_id": event_id})
    else:
        audit.record(None, "payment.paid_online", makerspace=payment.makerspace, target=payment,
                     meta={"provider": provider, "event_id": event_id})
    if differs(payment, minor, currency) and flags_on(payment):
        record_flag(payment, kind=PaymentCaptureFlag.Kind.MISMATCH, provider=provider,
                    provider_payment_id=capture_id, event_id=event_id,
                    minor=minor, currency=currency, prior_status=Payment.Status.PENDING)
    from apps.payments.documents import issue_receipt
    issue_receipt(payment)
    notify_payment(payment, "payment_received")
    resume_admission_after_settlement(payment)
    return payment


def flag_terminal_capture(payment, *, provider, capture_id, event_id, minor=0, currency=""):
    """Flag money for a charge that was cancelled, already paid offline, or paid by another capture.

    Waived charges keep their release-1 correction (promotion to paid_online with a
    receipt), so only these three states are flagged.
    """
    if not flags_on(payment):
        return None  # Release-1 behaviour: the audit-only paths in terminal_settlement.
    prior = payment.status
    if prior == Payment.Status.PAID_ONLINE and not (
            capture_id and {payment.external_payment_id, payment.stripe_payment_intent_id} - {None, ""}
            and capture_id not in {payment.external_payment_id, payment.stripe_payment_intent_id}):
        return None
    if prior not in (Payment.Status.CANCELED, Payment.Status.PAID_OFFLINE, Payment.Status.PAID_ONLINE):
        return None
    return flag_after_terminal(payment, provider=provider, provider_payment_id=capture_id or "", event_id=event_id,
                               minor=minor, currency=currency, prior_status=prior)


def fill_method_label(payment, label):
    """One-time fill from a later provider event (Stripe sends card details on the charge)."""
    if not label or payment.method_label:
        return False
    updated = Payment.objects.filter(pk=payment.pk, method_label="").update(method_label=label[:64])
    if updated:
        payment.method_label = label[:64]
    return bool(updated)
