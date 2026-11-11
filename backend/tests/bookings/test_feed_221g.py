"""Decision 221(g): stable busy DTSTAMP, and the public event venue prefers the linked booking's room."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from icalendar import Calendar
from rest_framework.test import APIClient

from apps.bookings.models import BookableSpace
from apps.events.models import Event
from apps.events.models_booking_decision import EventBookingDecision
from tests.bookings.test_busy_overlay import outage
from tests.bookings.test_member_booking_api import book, setup

pytestmark = pytest.mark.django_db


def _busy(url):
    return [event for event in Calendar.from_ical(APIClient().get(url).content).walk("VEVENT")
            if str(event["UID"]).startswith("busy-")]


def test_busy_block_dtstamp_derives_from_the_source_rows_never_the_clock():
    tenant, room, user, client = setup("feed-stamp")
    tenant.enabled_features = sorted(set(tenant.enabled_features or []) | {"bookings.room_maintenance"})  # the outage layer is a capability
    tenant.save(update_fields=["enabled_features"])
    mine = book(room, user)
    row = outage(room)
    url = client.post(reverse("member-booking-feed-settings", kwargs={"makerspace_slug": tenant.slug}),
                      {}, format="json").data["feed_url"]
    [first] = _busy(url)
    [second] = _busy(url)
    stamp = max(row.started_at, mine.calendar_updated_at).replace(microsecond=0)
    assert first["DTSTAMP"].dt == second["DTSTAMP"].dt == stamp


def _event_at(tenant, label):
    start = timezone.now() + timedelta(days=1)
    tenant.enabled_modules = sorted(set(tenant.enabled_modules or []) | {"events"})
    tenant.save(update_fields=["enabled_modules"])
    return Event.objects.create(makerspace=tenant, title="Bootcamp", starts_at=start, ends_at=start + timedelta(hours=2),
                                location=label, is_public=True, status=Event.Status.PUBLISHED)


def _venue_name(tenant, event):
    url = reverse("public-event-venue", kwargs={"makerspace_slug": tenant.slug, "public_token": event.public_token})
    return APIClient().get(url).json()["space"]["name"]


def _link(tenant, event, booking):
    EventBookingDecision.objects.create(makerspace=tenant, event=event, booking=booking,
                                        operation_id="00000000-0000-0000-0000-000000000221")


def test_venue_uses_the_linked_bookings_room_before_location_text():
    tenant, room, user, _ = setup("feed-venue", is_public=True)
    BookableSpace.objects.create(makerspace=tenant, name="Hall", approval_mode="instant", is_public=True)
    event = _event_at(tenant, "Hall")  # the text names the Hall; the booking holds the Room
    assert _venue_name(tenant, event) == "Hall"
    _link(tenant, event, book(room, user))
    assert _venue_name(tenant, event) == "Room"


def test_a_cancelled_linked_booking_or_a_private_room_falls_back_to_location_text():
    tenant, room, user, _ = setup("feed-venue-fallback", is_public=True)
    BookableSpace.objects.create(makerspace=tenant, name="Hall", approval_mode="instant", is_public=True)
    event = _event_at(tenant, "Hall")
    booking = book(room, user)
    _link(tenant, event, booking)
    booking.status = "cancelled"
    booking.save(update_fields=["status"])
    assert _venue_name(tenant, event) == "Hall"
    booking.status = "confirmed"
    booking.save(update_fields=["status"])
    BookableSpace.objects.filter(pk=room.pk).update(is_public=False)
    assert _venue_name(tenant, event) == "Hall"
