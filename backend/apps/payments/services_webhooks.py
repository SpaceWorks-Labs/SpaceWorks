from django.db import transaction
from django.db.models import Q

from apps.accounts import rbac
from apps.audit import services as audit
from apps.payments.checkout_expiry import forget_closed_checkout
from apps.payments.models import Payment
from apps.payments.services_refund_webhooks import (  # noqa: F401  (_record_once re-exported)
    STRIPE_REFUND_EVENT_TYPES,
    _record_once,
    _value,
    apply_razorpay_refund_event,
    apply_stripe_refund_event,
    claim_razorpay_event,
)
from apps.payments.terminal_settlement import (
    handle_razorpay_paid_after_terminal,
    handle_stripe_paid_after_terminal,
)
from apps.makerspaces.servability import is_servable
from apps.payments.method_labels import stripe_label
from apps.payments.online_settlement import flag_terminal_capture, settle_capture

STRIPE_DISPUTE_EVENT_TYPES = frozenset({
    "charge.dispute.created", "charge.dispute.updated", "charge.dispute.closed",
    "charge.dispute.funds_withdrawn", "charge.dispute.funds_reinstated",
})


def _stripe_amount(obj, event_type):
    """(minor, currency) the provider says it captured; (0, '') when it did not say."""
    key = "amount_total" if event_type.startswith("checkout.session.") else "amount_received"
    minor = _value(obj, key)
    if minor is None and key == "amount_received":
        minor = _value(obj, "amount")
    currency = _value(obj, "currency") or ""
    return (int(minor) if isinstance(minor, int) and not isinstance(minor, bool) else 0), str(currency).lower()


def apply_webhook_event(
    makerspace,
    event,
    *,
    provider=Payment.StripeProvider.RAW,
    connected_account_id=None,
):
    event_id = _value(event, "id")
    if not event_id or not is_servable(makerspace, allow_archived=True):
        return None
    event_type, data = _value(event, "type"), _value(event, "data") or {}
    obj = _value(data, "object") or {}
    if event_type in STRIPE_REFUND_EVENT_TYPES:
        return apply_stripe_refund_event(
            makerspace, event, provider=provider, connected_account_id=connected_account_id
        )
    if event_type in STRIPE_DISPUTE_EVENT_TYPES or event_type == "charge.succeeded":
        # Ingested only through the rail's webhook routes (lane L5): disputes become a
        # core-ledger record; a charge event only fills the payment method label.
        from apps.payments_rail.dispute_ingest import apply_stripe_side_event
        return apply_stripe_side_event(makerspace, event, provider=provider,
                                       connected_account_id=connected_account_id)
    if event_type not in {
        "checkout.session.completed",
        "checkout.session.async_payment_succeeded",
        "checkout.session.expired",
        "payment_intent.succeeded",
        "payment_intent.payment_failed",
        "checkout.session.async_payment_failed",
    }:
        return None
    # Paid means `payment_status == "paid"`, never a missing field (PAY-REVIEW 0.12.0). Real Stripe
    # always sends it; `no_payment_required` is not accepted either, because a Payment is always a
    # positive amount (DB check), so a session that took nothing can never settle one.
    if event_type == "checkout.session.completed" and _value(obj, "payment_status") != "paid":
        return None
    session_id = (
        _value(obj, "id")
        if event_type in {
            "checkout.session.completed",
            "checkout.session.async_payment_succeeded",
            "checkout.session.expired",
            "checkout.session.async_payment_failed",
        }
        else None
    )
    intent_id = _value(obj, "payment_intent") or (
        _value(obj, "id") if event_type in {"payment_intent.succeeded", "payment_intent.payment_failed"} else None
    )
    if not session_id and not intent_id:
        return None
    with transaction.atomic():
        identifiers = Q()
        if session_id:
            identifiers |= Q(stripe_checkout_session_id=session_id)
        if intent_id:
            identifiers |= Q(stripe_payment_intent_id=intent_id)
        payments = rbac.scope_notification_policy(
            Payment.objects.select_for_update(), makerspace_id=makerspace.pk,
        ).filter(provider=Payment.Provider.STRIPE, stripe_provider=provider)
        if connected_account_id is not None:
            payments = payments.filter(
                stripe_connected_account_id=connected_account_id
            )
        payment = payments.filter(identifiers).first()
        if payment is None:
            return None
        if not _record_once(makerspace, event_id):
            return None
        if event_type in {"payment_intent.payment_failed", "checkout.session.async_payment_failed"}:
            from apps.payments.failure_notifications import record_payment_failure
            return record_payment_failure(payment, event_id=event_id, provider="stripe")
        if event_type == "checkout.session.expired":
            payment.save(update_fields=[*forget_closed_checkout(payment), "updated_at"])
            audit.record(
                None,
                "payment.checkout_expired",
                makerspace=makerspace,
                target=payment,
                meta={"stripe_event_id": event_id},
            )
            return payment
        minor, currency = _stripe_amount(obj, event_type)
        if payment.status != Payment.Status.PENDING:
            flag_terminal_capture(payment, provider=Payment.Provider.STRIPE, capture_id=intent_id,
                                  event_id=event_id, minor=minor, currency=currency)
            return handle_stripe_paid_after_terminal(
                payment,
                event_id=event_id,
                intent_id=intent_id,
            )
        return settle_capture(payment, provider=Payment.Provider.STRIPE, capture_id=intent_id,
                              event_id=event_id, minor=minor, currency=currency, method_label=stripe_label(obj))


def apply_razorpay_webhook_event(makerspace, event):
    """Settle a VERIFIED Razorpay event. `event` is a providers.base.WebhookEvent.

    Same discipline as the Stripe path, and for the same reasons:

    * The row is found by the ids the provider echoed back, never by anything the payer
      supplied, and is locked before it is read.
    * Settlement happens **regardless of the live capability toggle**. A real charge must
      never be stranded because someone unticked a feature between checkout and callback.
    * A paid event after waiver corrects the ledger; one after offline settlement raises
      an explicit refund-required audit condition instead of silently double-settling.
    """
    if not is_servable(makerspace, allow_archived=True) or not event.event_id:
        return None
    if event.refund_id:
        return apply_razorpay_refund_event(makerspace, event)
    if event.dispute_id:
        from apps.payments_rail.dispute_ingest import apply_razorpay_dispute_event
        return apply_razorpay_dispute_event(makerspace, event)
    if not event.is_paid and not event.is_failed:
        # Non-payment events are not recorded: claiming their id would make a later
        # genuine settlement carrying the same delivery id read as a duplicate.
        return None
    with transaction.atomic():
        identifiers = Q()
        if event.order_id:
            identifiers |= Q(external_order_id=event.order_id)
        if event.payment_id:
            identifiers |= Q(external_payment_id=event.payment_id)
        if not identifiers:
            return None
        payment = (
            rbac.scope_notification_policy(Payment.objects.select_for_update(), makerspace_id=makerspace.pk)
            .filter(provider=Payment.Provider.RAZORPAY)
            .filter(identifiers)
            .first()
        )
        if payment is None:
            return None
        if not claim_razorpay_event(makerspace, event):
            return None
        if event.is_failed:
            from apps.payments.failure_notifications import record_payment_failure
            return record_payment_failure(payment, event_id=event.event_id, provider="razorpay")
        provider_payment_id = event.payment_id
        if payment.status != Payment.Status.PENDING:
            flag_terminal_capture(payment, provider=Payment.Provider.RAZORPAY, capture_id=provider_payment_id,
                                  event_id=event.event_id, minor=event.amount_minor, currency=event.currency)
            return handle_razorpay_paid_after_terminal(
                payment,
                event_id=event.event_id,
                payment_id=provider_payment_id,
                amount_minor=event.amount_minor,
                currency=event.currency,
            )
        return settle_capture(payment, provider=Payment.Provider.RAZORPAY, capture_id=provider_payment_id,
                              event_id=event.event_id, minor=event.amount_minor, currency=event.currency,
                              method_label=event.method_label)


# Explicit compatibility exports; callers keep the existing webhook import paths.
from apps.payments.services_connect_webhooks import (  # noqa: E402,F401
    apply_connect_webhook_event, _apply_account_event, _event_is_stale,
)
