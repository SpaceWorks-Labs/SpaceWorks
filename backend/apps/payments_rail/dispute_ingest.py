"""Provider-shaped webhook branches for disputes and method labels (lane L5).

Reached only through the rail's webhook routes, which a `payments_rail` tombstone
withdraws. Each branch finds the charge by the ids the provider echoed back, under the
Payment lock, claims the event id once, and hands a normalized record to the core
ledger (`payments.services_disputes`). Nothing here moves money.
"""

from datetime import datetime, timezone

from django.db import transaction

from apps.accounts import rbac
from apps.payments.method_labels import stripe_label
from apps.payments.models import Payment
from apps.payments.online_settlement import fill_method_label
from apps.payments.services_disputes import record_dispute_event
from apps.payments.services_refund_webhooks import _record_once, _value, claim_razorpay_event


def _locked(makerspace, **lookup):
    return rbac.scope_notification_policy(
        Payment.objects.select_for_update(), makerspace_id=makerspace.pk,
    ).filter(**lookup).first()


def apply_stripe_side_event(makerspace, event, *, provider, connected_account_id=None):
    event_id, event_type = _value(event, "id"), _value(event, "type") or ""
    obj = _value(_value(event, "data") or {}, "object") or {}
    intent_id = _value(obj, "payment_intent")
    if not event_id or not intent_id:
        return None
    lookup = {"provider": Payment.Provider.STRIPE, "stripe_provider": provider, "stripe_payment_intent_id": intent_id}
    if connected_account_id is not None:
        lookup["stripe_connected_account_id"] = connected_account_id
    with transaction.atomic():
        payment = _locked(makerspace, **lookup)
        if payment is None or not _record_once(makerspace, event_id):
            return None
        if event_type == "charge.succeeded":
            fill_method_label(payment, stripe_label(obj))
            return payment
        due = _value(_value(obj, "evidence_details") or {}, "due_by")
        return record_dispute_event(
            payment, provider="stripe", dispute_id=_value(obj, "id") or "", raw_status=_value(obj, "status"),
            event_id=event_id, minor=_value(obj, "amount") or 0, currency=_value(obj, "currency") or "",
            reason=_value(obj, "reason") or "",
            evidence_due_at=datetime.fromtimestamp(due, tz=timezone.utc) if isinstance(due, int) else None)


def apply_razorpay_dispute_event(makerspace, event):
    if not event.payment_id:
        return None
    with transaction.atomic():
        payment = _locked(makerspace, provider=Payment.Provider.RAZORPAY, external_payment_id=event.payment_id)
        if payment is None or not claim_razorpay_event(makerspace, event):
            return None
        return record_dispute_event(
            payment, provider="razorpay", dispute_id=event.dispute_id, raw_status=event.dispute_status,
            event_id=event.event_id, minor=event.dispute_amount_minor, currency=event.currency,
            reason=event.dispute_reason)
