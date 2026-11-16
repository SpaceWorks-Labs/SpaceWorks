"""Open items B9: a venue fee may not bill a room that an unlinked live booking already holds."""
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.bookings.models import BookableSpace, Booking
from apps.events.models import Event, EventVenueFee
from tests.events.collab_helpers import client_for
from tests.events.orders_helpers import l6_space, make_staff, verified

pytestmark = pytest.mark.django_db


def _draft(space):
    starts = timezone.now() + timedelta(days=2)
    return Event.objects.create(makerspace=space, title="Outside meetup", starts_at=starts, ends_at=starts + timedelta(hours=3),
                                registration_audience="accounts", is_public=True, status="draft")


def _book(room, event, status="confirmed", **extra):
    return Booking.objects.create(space=room, name="Booker", email="booker@example.test", status=status,
                                  starts_at=event.starts_at + timedelta(hours=1), ends_at=event.ends_at + timedelta(hours=1), **extra)


def _put(staff, event, body):
    return client_for(staff).put(reverse("admin-event-venue-fee", kwargs={"pk": event.pk}), body, format="json")


@pytest.mark.parametrize("status", ["pending", "confirmed"])
def test_live_overlapping_booking_of_the_same_room_refuses_the_fee(status):
    space = l6_space("clash-b9")
    staff, organiser = make_staff(space), verified("clash-organiser")
    room = BookableSpace.objects.create(makerspace=space, name="Hall")
    event = _draft(space)
    _book(room, event, status=status)
    response = _put(staff, event, {"payer_id": organiser.pk, "mode": "inherit", "room_id": room.pk})
    assert response.status_code == 409 and response.data["code"] == "venue_room_already_booked"
    assert not EventVenueFee.objects.exists()


@pytest.mark.parametrize("status", ["cancelled", "rejected", "completed"])
def test_dead_bookings_and_other_rooms_do_not_block(status):
    space = l6_space("clash-ok")
    staff, organiser = make_staff(space), verified("clash-ok-organiser")
    room, other = BookableSpace.objects.create(makerspace=space, name="Hall"), BookableSpace.objects.create(makerspace=space, name="Lab")
    event = _draft(space)
    _book(room, event, status=status)
    _book(other, event)
    response = _put(staff, event, {"payer_id": organiser.pk, "mode": "inherit", "room_id": room.pk})
    assert response.status_code == 200, response.data


def test_no_room_never_checks_bookings():
    space = l6_space("clash-none")
    staff, organiser = make_staff(space), verified("clash-none-organiser")
    room = BookableSpace.objects.create(makerspace=space, name="Hall")
    event = _draft(space)
    _book(room, event)
    assert _put(staff, event, {"payer_id": organiser.pk, "mode": "free"}).status_code == 200


def test_charge_now_refuses_when_a_booking_appeared_after_configuring():
    space = l6_space("clash-late")
    staff, organiser = make_staff(space), verified("clash-late-organiser")
    room = BookableSpace.objects.create(makerspace=space, name="Hall")
    event = _draft(space)
    assert _put(staff, event, {"payer_id": organiser.pk, "mode": "custom", "basis": "flat", "amount": "20.00",
                               "room_id": room.pk}).status_code == 200
    _book(room, event)
    response = client_for(staff).post(reverse("admin-event-venue-fee-charge", kwargs={"pk": event.pk}), {}, format="json")
    assert response.status_code == 409 and response.data["code"] == "venue_room_already_booked"
    assert EventVenueFee.objects.get().status == "configured"
