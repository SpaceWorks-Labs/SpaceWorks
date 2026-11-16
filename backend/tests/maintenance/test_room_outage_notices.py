"""P2-4: a room outage over existing bookings is told to each booker and to booking staff.

Account bookers get their own `bookings.room_outage` envelope naming only their booking; staff
get one summary per outage with a count, never who booked. Silent while Bookings is off, and
no longer eligible once the outage ends.
"""
from datetime import timedelta

import pytest

from apps.bookings.services_bookings import create_booking
from apps.integrations.models_contract import NotificationEnvelope
from apps.maintenance.repairs import service_state
from apps.maintenance.repairs.room_outage_notices import eligible
from tests.machines.certification_helpers import _member
from tests.maintenance.l16_helpers import tomorrow, world
from tests.module_helpers import disable_module

pytestmark = pytest.mark.django_db


def notices(**filters):
    return list(NotificationEnvelope.objects.filter(feature="bookings", event="room_outage", **filters)
                .order_by("pk"))


def two_bookings(w, slug):
    first, _ = _member(w.space, f"{slug}-a")
    second, _ = _member(w.space, f"{slug}-b")
    start, end = tomorrow()
    create_booking(w.room, member=first, actor=first, starts_at=start, ends_at=end)
    create_booking(w.room, member=second, actor=second, starts_at=start + timedelta(hours=2),
                   ends_at=end + timedelta(hours=2))
    return first, second


def take_out(w):
    return service_state.set_state(w.manager, w.space, subject_type="bookable_space", subject=w.room,
                                   in_service=False, reason="Flooded")


def test_each_booker_hears_about_their_own_booking_and_staff_get_one_summary():
    w = world("outage-notice")
    first, second = two_bookings(w, "outage-notice")
    result = take_out(w)
    owners = notices(audience="requester")
    assert sorted(row.recipient_id for row in owners) == sorted([first.pk, second.pk])
    for row in owners:
        other = second if row.recipient_id == first.pk else first
        assert other.username not in row.message_body and f"#{row.context['booking_id']}" in row.message_body
    staff = notices(audience="staff")
    assert w.manager.pk in {row.recipient_id for row in staff}
    assert len([row for row in staff if row.recipient_id == w.manager.pk]) == 1
    assert "2 bookings" in staff[0].message_body
    assert first.username not in staff[0].message_body and second.username not in staff[0].message_body
    assert all(eligible(row) for row in owners + staff)
    service_state.set_state(w.manager, w.space, subject_type="bookable_space", subject=w.room, in_service=True)
    assert not any(eligible(row) for row in owners + staff)
    assert result["outage"] is not None


def test_no_bookings_means_no_staff_notice():
    w = world("outage-empty")
    take_out(w)
    assert notices() == []


def test_bookings_off_is_silent():
    w = world("outage-off")
    two_bookings(w, "outage-off")
    disable_module(w.space, "bookings")
    w.space.refresh_from_db()
    from apps.maintenance.models import RoomOutage
    from apps.maintenance.repairs.notify import bookers_outage
    from apps.maintenance.repairs.room_outages import affected_bookings
    outage = RoomOutage.objects.create(makerspace=w.space, room=w.room, mode="block", reason="Flooded")
    bookers_outage(outage, list(affected_bookings(outage)))
    assert notices() == []
