"""Shared builders for the E-B5 tests."""
from datetime import time

from django.utils import timezone

from apps.events.models import EventSeries
from tests.events.collab_helpers import make_event, make_member, make_space, make_staff


def world(slug, *features, capacity=0, amount=None):
    space = make_space(slug)
    # `events.pay_window` requires `events.orders`; a feature whose requirement is off reads as off.
    from tests.events.orders_helpers import L6_FEATURES
    needs = ("events.ticket_types", *L6_FEATURES) if "events.pay_window" in features else ()
    space.enabled_features = ["charges.enabled", "charges.events", *needs, *features]
    space.save(update_fields=["enabled_features"])
    event = make_event(space, is_public=True)
    event.capacity = capacity
    if amount:
        event.payment_amount = amount
    event.save()
    return space, event, make_staff(space)


def attach_series(event, space, **fields):
    series = EventSeries.objects.create(
        makerspace=space, title="Weekly", recurrence_timezone="UTC", dtstart_local_date=timezone.now().date(),
        dtstart_local_time=time(12), recurrence_rule="FREQ=DAILY;COUNT=2", duration_minutes=60,
        status="published", **fields)
    event.series, event.series_revision, event.series_occurrence_key = series, series.revision, "k1"
    event.save(update_fields=["series", "series_revision", "series_occurrence_key"])
    return series


def verified_member(space, name):
    member = make_member(space, name)
    member.email_verified_at = timezone.now()
    member.save(update_fields=["email_verified_at"])
    return member
