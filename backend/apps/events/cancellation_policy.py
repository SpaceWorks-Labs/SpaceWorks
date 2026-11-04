"""Shared cancellation presentation, and the per-event refund override (release 2 L6, G34).

The override is read by `payments.refund_policy.area_policy`, the one hook in the
policy lookup. Once the event has sold anything the override may only become MORE
generous -- a shorter or equal full window, a shorter or equal partial window, an equal
or higher partial percentage, an equal or lower fee -- so a buyer is never worse off
than the policy shown before they paid (`policy_less_generous`).
"""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.events.models import Event, EventRegistration

OVERRIDE_FIELDS = ("full_before_minutes", "partial_before_minutes", "partial_percent", "cancellation_fee")


def cancellation_cutoff(event):
    return event.starts_at - timedelta(hours=event.cancellation_cutoff_hours or 0)


def member_can_cancel(registration, *, now=None):
    return (
        registration.event.status == Event.Status.PUBLISHED
        and registration.status in (
            EventRegistration.Status.PENDING_APPROVAL,
            EventRegistration.Status.REGISTERED,
            EventRegistration.Status.WAITLISTED,
        )
        and (now or timezone.now()) < cancellation_cutoff(registration.event)
    )


def payment_event(payment):
    """The event a registration, order or venue-fee charge pays for (None for a series pass)."""
    from .models import EventOrder, EventVenueFee
    if payment.subject_type == "event_registration":
        return Event.objects.filter(registrations__pk=payment.subject_id).first()
    if payment.subject_type == "event_order":
        order = EventOrder.objects.filter(pk=payment.subject_id).select_related("event").first()
        return order.event if order else None
    if payment.subject_type == "event_venue_fee":
        fee = EventVenueFee.objects.filter(pk=payment.subject_id).select_related("event").first()
        return fee.event if fee else None
    return None


def subject_starts_at(payment):
    event = payment_event(payment)
    return event.starts_at if event else None


def override_settings(event):
    from apps.makerspaces.platform import feature_enabled
    from .models import EventSalesSettings
    if event is None or not feature_enabled(event.makerspace, "events.refund_override"):
        return None
    return EventSalesSettings.objects.filter(event=event, refund_override=True).first()


def override_policy(payment):
    """An unsaved `RefundPolicy` shaped from the event's override, or None to use the space's."""
    from apps.payments.models_refund_cases import RefundPolicy
    if payment.subject_type == "event_venue_fee":
        return None  # hosting fees go back only by a staff decision (#59)
    row = override_settings(payment_event(payment))
    if row is None:
        return None
    return RefundPolicy(makerspace_id=payment.makerspace_id, area=RefundPolicy.Area.EVENTS,
                        **{field: getattr(row, field) for field in OVERRIDE_FIELDS})


def has_sales(event):
    """True once anything was paid for this event: a registration charge or a ticket order."""
    from apps.payments.models import Payment
    from .models import EventOrder
    settled = (Payment.Status.PAID_ONLINE, Payment.Status.PAID_OFFLINE)
    return (Payment.objects.filter(makerspace=event.makerspace, subject_type="event_registration",
                                   subject_id__in=event.registrations.values("pk"), status__in=settled).exists()
            or EventOrder.objects.filter(event=event, status=EventOrder.Status.PAID).exists())


def less_generous(old, new):
    """The fields where `new` would treat a buyer worse than `old`."""
    worse = []
    if new["full_before_minutes"] > old["full_before_minutes"]:
        worse.append("full_before_minutes")
    if new["partial_before_minutes"] > old["partial_before_minutes"]:
        worse.append("partial_before_minutes")
    if new["partial_percent"] < old["partial_percent"]:
        worse.append("partial_percent")
    if new["cancellation_fee"] > old["cancellation_fee"]:
        worse.append("cancellation_fee")
    return worse


def current_terms(event, row):
    """What a buyer was shown: this event's override, else the space's events policy."""
    from apps.payments.models_refund_cases import RefundPolicy
    if row is not None and row.refund_override:
        return {field: getattr(row, field) for field in OVERRIDE_FIELDS}, True
    policy = RefundPolicy.objects.filter(makerspace=event.makerspace, area="events", plan__isnull=True).first()
    if policy is None:
        return None, False
    return {field: getattr(policy, field) for field in OVERRIDE_FIELDS}, False


@transaction.atomic
def set_override(event, *, actor, enabled, values, policy_text=""):
    """Write the override; refuse a less generous one after the first sale."""
    from apps.audit.services import record
    from rest_framework.exceptions import ValidationError
    from .feature_gates import require_feature
    from .models import EventSalesSettings
    from .orders_errors import OrderRefused
    require_feature(event, "events.refund_override")
    row, _ = EventSalesSettings.objects.select_for_update().get_or_create(
        event=event, defaults={"makerspace": event.makerspace})
    if values["full_before_minutes"] < values["partial_before_minutes"]:
        raise ValidationError({"partial_before_minutes": "The partial window must end before the full window."})
    if has_sales(event):
        old, _overridden = current_terms(event, row)
        if not enabled and row.refund_override:
            raise OrderRefused("policy_less_generous", "The event's own policy cannot be removed after the first sale.")
        if enabled and old is not None and less_generous(old, values):
            raise OrderRefused("policy_less_generous",
                               "After the first sale the refund policy may only become more generous.",
                               fields=less_generous(old, values))
    before = {field: str(getattr(row, field)) for field in OVERRIDE_FIELDS}
    row.refund_override = bool(enabled)
    for field in OVERRIDE_FIELDS:
        setattr(row, field, values[field])
    row.policy_text = (policy_text or "").strip()[:2000]
    row.updated_by = actor
    row.save()
    record(actor, "event.refund_policy_overridden", makerspace=event.makerspace, target=event,
           meta={"enabled": row.refund_override, "before": before,
                 "after": {field: str(getattr(row, field)) for field in OVERRIDE_FIELDS}})
    return row


def policy_summary(event):
    """The refund policy a buyer sees before paying: the terms, and the organiser's words."""
    from .models import EventSalesSettings
    row = override_settings(event)
    text = EventSalesSettings.objects.filter(event=event).values_list("policy_text", flat=True).first() or ""
    terms, overridden = current_terms(event, row)
    return {"text": text, "overridden": overridden,
            "terms": {key: str(value) for key, value in terms.items()} if terms else None}
