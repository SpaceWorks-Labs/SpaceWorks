"""Decision 216: a room outage, machine repair or closure meeting an event's venue is flagged, never applied.

The booking-link GET carries read-only `conflicts` (each layer gone with its switch; detail only for
room/service-state authority), linking refuses a block-mode outage over the event's window, a new
outage over a linked booking tells the event's organizers once, and the outage dialog can preview
the bookings and events it would meet before saving.
"""
from datetime import timedelta
from uuid import uuid4

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.bookings import services_bookings
from apps.bookings.models import Booking
from apps.events import booking_decision_service
from apps.events.booking_decision_service import DecisionConflict
from apps.events.models import Event
from apps.events.venue_conflicts import conflicts
from apps.integrations.models_contract import NotificationEnvelope
from apps.maintenance.models import RoomOutage
from tests.encryption.conftest import enabled_encryption
from tests.events.orders_helpers import l6_space, make_staff
from tests.events.test_booking_decision_replacement import link_state, linked
from tests.maintenance.l16_helpers import switch
from tests.module_helpers import disable_module
from tests.payments.test_track3_booking_event_charging import bookable, member_with_phone

pytestmark = pytest.mark.django_db(transaction=True)
ROOM_LAYERS = ("bookings.room_maintenance", "bookings.room_repairs")


def outage(room, *, mode="block", reason="Flooded basement"):
    return RoomOutage.objects.create(makerspace=room.makerspace, room=room, mode=mode, reason=reason,
                                     started_at=timezone.now(), expected_back_at=timezone.now() + timedelta(days=5))


def on(maker):
    return switch(maker, on=ROOM_LAYERS)


def organizer_notices(**filters):
    return list(NotificationEnvelope.objects.filter(
        feature="events", event="linked_booking_changed", source_kind="events.linked_venue_outage", **filters))


def test_block_outage_is_a_conflict_with_detail_and_vanishes_with_the_switch():
    maker, _staff, _member, event, room, booking, _decision, client = linked("vc-block")
    on(maker)
    outage(room)
    [row] = link_state(client, maker, event)["conflicts"]
    assert (row["code"], row["severity"], row["reason"]) == ("room_out_of_service", "block", "Flooded basement")
    booking.refresh_from_db()
    assert booking.status in (Booking.Status.PENDING, Booking.Status.CONFIRMED)  # nothing is cancelled
    switch(maker, off=ROOM_LAYERS)
    assert link_state(client, maker, event)["conflicts"] == []


def test_warn_outage_is_a_warning_and_a_cancelled_event_has_no_conflicts():
    maker, _staff, _member, event, room, _booking, _decision, client = linked("vc-warn")
    on(maker)
    outage(room, mode="warn")
    assert [(row["code"], row["severity"]) for row in link_state(client, maker, event)["conflicts"]] == [
        ("room_outage_warning", "warning")]
    Event.objects.filter(pk=event.pk).update(status=Event.Status.CANCELLED)
    assert link_state(client, maker, event)["conflicts"] == []


def test_event_outside_recorded_hours_is_a_space_closed_warning_never_a_refusal():
    maker, _staff, _member, event, _room, _booking, _decision, client = linked("vc-hours")
    assert link_state(client, maker, event)["conflicts"] == []  # no hours recorded: always open
    # An empty weekly schedule means open every day (local_time._day_intervals), so a closure needs every
    # weekday spelled out: the space opens for one hour a day and the event window spills outside it.
    from apps.makerspaces.local_time import WEEKDAYS
    maker.timezone = "UTC"
    maker.opening_hours = {"weekly": {day: [{"start": "09:00", "end": "09:30"}] for day in WEEKDAYS}, "exceptions": {}}
    maker.save(update_fields=["timezone", "opening_hours"])
    rows = link_state(client, maker, event)["conflicts"]
    assert rows and {(row["code"], row["severity"]) for row in rows} == {("space_closed", "warning")}


def test_a_viewer_without_room_or_service_authority_sees_only_the_generic_conflict():
    maker, _staff, member, _event, room, booking, _decision, _client = linked("vc-privacy")
    on(maker)
    outage(room, reason="Asbestos survey")
    rows = conflicts(member, booking, booking.starts_at, booking.ends_at)
    assert rows == [{"code": "room_out_of_service", "severity": "block"}]


def _unlinked(slug):
    maker = l6_space(slug)
    maker.enabled_modules = sorted(set(maker.enabled_modules) | {"bookings"})
    maker.save(update_fields=["enabled_modules"])
    staff, member = make_staff(maker), member_with_phone(slug + "-member", maker)
    start = timezone.now() + timedelta(days=2)
    event = Event.objects.create(makerspace=maker, title="Robot night", starts_at=start,
                                 ends_at=start + timedelta(hours=1), status=Event.Status.DRAFT)
    room = bookable(maker, approval_mode="approve", amount="0")
    with enabled_encryption():
        booking = services_bookings.create_booking(room, starts_at=start, ends_at=event.ends_at,
                                                   member=member, actor=member)
    return maker, staff, event, room, booking


def _link(maker, staff, event, booking):
    with enabled_encryption():
        return booking_decision_service.create_decision(
            staff, maker, event.pk, booking_id=booking.pk, operation_id=uuid4(), expected_generation=None,
            expected_revision=0, expected_events_epoch=maker.loan_context_generations["events"],
            expected_bookings_epoch=maker.loan_context_generations["bookings"])


def test_linking_refuses_a_block_outage_over_the_event_but_a_warn_outage_links():
    maker, staff, event, room, booking = _unlinked("vc-link")
    on(maker)
    row = outage(room)
    with pytest.raises(DecisionConflict) as refused:
        _link(maker, staff, event, booking)
    assert refused.value.detail["code"] == "room_out_of_service"
    RoomOutage.objects.filter(pk=row.pk).update(mode="warn")
    decision, replayed = _link(maker, staff, event, booking)
    assert decision.booking_id == booking.pk and replayed is False


def test_linking_ignores_an_outage_while_room_maintenance_is_off():
    maker, staff, event, room, booking = _unlinked("vc-link-off")
    switch(maker, off=ROOM_LAYERS)
    outage(room)
    decision, _ = _link(maker, staff, event, booking)
    assert decision.booking_id == booking.pk


def _take_out(staff, maker, room):
    from apps.maintenance.repairs import service_state
    with enabled_encryption():
        return service_state.set_state(staff, maker, subject_type="bookable_space", subject=room,
                                       in_service=False, reason="Flooded basement")


def test_a_new_outage_over_a_linked_booking_tells_event_staff_once_without_reason_or_booker():
    maker, staff, member, event, room, booking, _decision, _client = linked("vc-notice")
    on(maker)
    result = _take_out(staff, maker, room)
    rows = organizer_notices()
    assert staff.pk in {row.recipient_id for row in rows if row.audience == "staff"}
    assert member.pk not in {row.recipient_id for row in rows}
    assert {row.source_id for row in rows} == {str(event.pk)}
    assert rows[0].context["outage_id"] == result["outage"].pk and rows[0].context["booking_id"] == booking.pk
    for row in rows:
        assert "Flooded" not in row.message_body and member.username not in row.message_body
    from apps.events.linked_outage_notices import notify_organizers, staff_eligible
    assert all(staff_eligible(row) for row in rows if row.audience == "staff")
    booking.refresh_from_db()
    notify_organizers(booking, result["outage"])  # idempotent per outage and event
    assert len(organizer_notices()) == len(rows)
    RoomOutage.objects.filter(pk=result["outage"].pk).update(ended_at=timezone.now())
    assert not any(staff_eligible(row) for row in rows)


def test_no_organizer_notice_while_events_is_off():
    maker, staff, _member, _event, room, _booking, _decision, _client = linked("vc-notice-off")
    on(maker)
    disable_module(maker, "events")
    maker.refresh_from_db()
    _take_out(staff, maker, room)
    assert organizer_notices() == []


def _impact(user, maker, room):
    client = APIClient()
    client.force_authenticate(user)
    url = reverse("admin-room-outage-impact", kwargs={"makerspace_id": maker.pk})
    with enabled_encryption():
        return client.get(url, {"room_id": room.pk})


def test_outage_impact_preview_lists_bookings_and_event_titles_and_writes_nothing():
    maker, staff, _member, event, room, booking, _decision, _client = linked("vc-impact")
    on(maker)
    response = _impact(staff, maker, room)
    assert response.status_code == 200, response.data
    assert response.data["booking_count"] == 1 and [row["id"] for row in response.data["bookings"]] == [booking.pk]
    assert response.data["events"] == [{"event_id": event.pk, "title": event.title, "event_status": event.status}]
    assert response.data["other_event_bookings"] == 0 and response.data["already_out_of_service"] is False
    assert not RoomOutage.objects.filter(room=room).exists()
    assert organizer_notices() == []


def test_outage_impact_hides_event_titles_from_a_viewer_who_cannot_see_the_event(monkeypatch):
    maker, staff, _member, event, room, _booking, _decision, _client = linked("vc-impact-hidden")
    on(maker)
    from apps.events import event_authority
    real = event_authority.can
    monkeypatch.setattr(event_authority, "can", lambda actor, row, *a, **kw: False if row.pk == event.pk
                        else real(actor, row, *a, **kw))
    response = _impact(staff, maker, room)
    assert response.status_code == 200
    assert response.data["events"] == [] and response.data["other_event_bookings"] == 1
    assert event.title.encode() not in response.content


def test_outage_impact_refuses_a_user_without_service_state_authority():
    maker, _staff, _member, _event, room, _booking, _decision, _client = linked("vc-impact-deny")
    on(maker)
    outsider = User.objects.create_user(username="vc-impact-outsider", access_status="active")
    assert _impact(outsider, maker, room).status_code in (403, 404)
