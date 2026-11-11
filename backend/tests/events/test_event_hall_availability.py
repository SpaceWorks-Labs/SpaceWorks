"""Decision 216: the hall an event books uses the Bookings calendar -- availability, holds and labels.

Bookings owns availability: the staff picker reads the same occupancy the public view reads,
admission still refuses conflicts, a pending booking holds nothing, and the linked event is
named only to a viewer who may see it. Event time drift and cancellation are flagged on the
link, never applied to the booking or its debt.
"""
from datetime import timedelta

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.rbac import Action
from apps.bookings import services_bookings, staff_availability
from apps.bookings.exceptions import BookingConflict
from apps.bookings.models import Booking
from apps.events.models import Event
from apps.payments.models import Payment
from tests.account_split_g2_helpers import staff_for_actions
from tests.encryption.conftest import enabled_encryption
from tests.events.test_booking_decision_replacement import body, link_state, linked, replace
from tests.payments.test_track3_booking_event_charging import member_with_phone

pytestmark = pytest.mark.django_db(transaction=True)


def client_for(actor):
    client = APIClient()
    client.force_authenticate(actor)
    return client


def availability(client, room, start, end):
    url = reverse("admin-space-booking-availability", kwargs={"pk": room.pk})
    with enabled_encryption():
        return client.get(url, {"starts_at": start.isoformat(), "ends_at": end.isoformat()})


def listed(client, room):
    url = reverse("admin-space-booking-list", kwargs={"pk": room.pk})
    with enabled_encryption():
        response = client.get(url)
    assert response.status_code == 200, response.data
    return {row["id"]: row for row in response.data["results"]}


def test_confirmed_event_booking_blocks_the_room_and_admission_refuses_a_conflict(monkeypatch):
    maker, staff, member, event, room, original, _decision, client = linked("hall-confirmed", approval_mode="instant")
    assert original.status == Booking.Status.CONFIRMED
    reads = []
    real = staff_availability.confirmed_occupancy
    monkeypatch.setattr(staff_availability, "confirmed_occupancy",
                        lambda *args: reads.append(args) or real(*args))
    response = availability(client, room, event.starts_at, event.ends_at)
    assert response.status_code == 200, response.data
    assert reads, "the staff picker must read the shared Bookings occupancy"
    data = response.data
    assert data["opening_intervals"], "an empty schedule is open all day"
    assert [row["booking_id"] for row in data["busy"]] == [original.pk]
    assert data["busy"][0]["label"] == {"kind": "event", "event_id": event.pk, "title": "Workshop",
                                        "event_status": "draft"}
    assert data["requested"]["conflict"] is True and data["requested"]["holds_room_on_create"] is True
    other = member_with_phone("hall-confirmed-other", maker)
    before = Booking.objects.count()
    with enabled_encryption(), pytest.raises(BookingConflict):
        services_bookings.create_booking(room, starts_at=event.starts_at, ends_at=event.ends_at,
                                         member=other, actor=staff)
    assert Booking.objects.count() == before


def test_a_pending_event_booking_holds_nothing_but_is_listed():
    maker, _staff, _member, event, room, original, _decision, client = linked("hall-pending")
    assert original.status == Booking.Status.PENDING
    data = availability(client, room, event.starts_at, event.ends_at).data
    assert data["busy"] == []
    assert [row["booking_id"] for row in data["pending"]] == [original.pk]
    assert data["pending"][0]["label"]["title"] == "Workshop"
    assert data["requested"]["conflict"] is False and data["requested"]["holds_room_on_create"] is False


def test_the_calendar_names_the_event_only_to_a_viewer_who_may_see_it():
    maker, _staff, _member, event, room, original, _decision, client = linked("hall-labels", approval_mode="instant")
    assert listed(client, room)[original.pk]["linked_event"]["title"] == "Workshop"
    rooms_only, _ = staff_for_actions(maker, "hall-labels-rooms", (Action.MANAGE_BOOKINGS,))
    viewer = client_for(rooms_only)
    assert listed(viewer, room)[original.pk]["linked_event"] == {"kind": "reserved"}
    busy = availability(viewer, room, event.starts_at, event.ends_at).data["busy"]
    assert busy[0]["label"] == {"kind": "reserved"}
    assert "Workshop" not in str(busy)


def test_a_replacement_booking_keeps_the_event_label():
    maker, staff, member, event, room, original, _decision, client = linked("hall-replaced")
    with enabled_encryption():
        services_bookings.reject_booking(original, actor=staff, reason="Double booked")
    replacement = replace(client, maker, event, body(room, member, original)).data["booking_id"]
    rows = listed(client, room)
    assert rows[replacement]["linked_event"]["event_id"] == event.pk
    assert rows[original.pk]["linked_event"]["event_id"] == event.pk


def test_event_time_drift_is_flagged_and_the_booking_is_not_moved():
    maker, _staff, _member, event, _room, original, _decision, client = linked("hall-drift")
    state = link_state(client, maker, event)
    assert state["coverage"] == "covers" and state["current_space_id"] == original.space_id
    Event.objects.filter(pk=event.pk).update(ends_at=event.ends_at + timedelta(hours=1))
    state = link_state(client, maker, event)
    assert state["coverage"] == "not_covered" and state["sync"] == "different"
    moved = Booking.objects.get(pk=original.pk)
    assert (moved.starts_at, moved.ends_at, moved.status) == (original.starts_at, original.ends_at, original.status)


def test_a_cancelled_event_is_flagged_and_keeps_its_booking_and_debt():
    maker, _staff, _member, event, room, original, _decision, client = linked("hall-cancelled", approval_mode="instant")
    debt = Payment.objects.get(makerspace=maker, subject_type=Payment.SubjectType.BOOKING, subject_id=original.pk)
    Event.objects.filter(pk=event.pk).update(status=Event.Status.CANCELLED)
    state = link_state(client, maker, event)
    assert state["event_status"] == "cancelled" and state["replaceable"] is False
    assert listed(client, room)[original.pk]["linked_event"]["event_status"] == "cancelled"
    original.refresh_from_db()
    refreshed = Payment.objects.get(pk=debt.pk)
    assert original.status == Booking.Status.CONFIRMED
    assert (refreshed.status, refreshed.amount) == (debt.status, debt.amount)


def test_events_off_reads_every_booking_as_ordinary(monkeypatch):
    maker, _staff, _member, event, room, original, _decision, client = linked("hall-events-off", approval_mode="instant")
    maker.enabled_modules = [key for key in maker.enabled_modules if key != "events"]
    maker.save(update_fields=["enabled_modules"])
    assert listed(client, room)[original.pk]["linked_event"] is None
    assert availability(client, room, event.starts_at, event.ends_at).data["busy"][0]["label"] == {"kind": "booking"}
    maker.enabled_modules = sorted(set(maker.enabled_modules) | {"events"})
    maker.save(update_fields=["enabled_modules"])
    import apps.separability.tombstones as tombstones
    monkeypatch.setattr(tombstones, "app_is_tombstoned", lambda label: label == "events")
    assert listed(client, room)[original.pk]["linked_event"] is None


def test_bookings_off_withdraws_the_staff_picker():
    maker, _staff, _member, event, room, _original, _decision, client = linked("hall-bookings-off")
    maker.enabled_modules = [key for key in maker.enabled_modules if key != "bookings"]
    maker.save(update_fields=["enabled_modules"])
    assert availability(client, room, event.starts_at, event.ends_at).status_code in (400, 403, 404)


def test_the_picker_refuses_an_unbounded_window():
    _maker, _staff, _member, event, room, _original, _decision, client = linked("hall-window")
    assert availability(client, room, event.starts_at, event.starts_at + timedelta(days=15)).status_code == 400
    assert availability(client, room, event.ends_at, event.starts_at).status_code == 400
