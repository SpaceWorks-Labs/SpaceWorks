"""Staff "Related" block on a live presence session: event, booking arrival, machine sessions (decision 216 #13)."""
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.bookings.models import BookableSpace, Booking
from apps.events.models import EventRegistration
from apps.presence.models import PresenceSession
from tests.events.ticketing_helpers import open_event
from tests.machines.session_helpers import open_session, session_world
from tests.return_helpers import authenticated_client, make_member

pytestmark = pytest.mark.django_db(transaction=True)


def _world(slug):
    w = session_world(slug, billing=False)
    w.space.enabled_modules = sorted(set(w.space.enabled_modules) | {"presence", "events", "bookings", "machines"})
    w.space.save(update_fields=["enabled_modules"])
    now = timezone.now()
    event = open_event(w.space)
    registration = EventRegistration.objects.create(
        event=event, member=w.member, name="Maker", email=w.member.email, phone="12345678",
        status=EventRegistration.Status.ATTENDED)
    PresenceSession.objects.filter(account=w.member, makerspace=w.space, ended_at=None).update(
        event_registration=registration, status="attending_event")
    resource = BookableSpace.objects.create(makerspace=w.space, name="Workshop room")
    booking = Booking.objects.create(
        space=resource, member=w.member, name="Maker", email=w.member.email, status="confirmed",
        starts_at=now - timedelta(minutes=30), ends_at=now + timedelta(hours=1), arrived_at=now - timedelta(minutes=5))
    machine_session = open_session(w, minutes_ago=3)
    return w, event, booking, machine_session


def _get(w, actor=None):
    url = reverse("admin-presence-related", kwargs={"makerspace_id": w.space.pk, "account_id": w.member.pk})
    return authenticated_client(actor or w.staff).get(url)


def test_manager_sees_event_booking_and_machine_sessions_for_the_present_person():
    w, event, booking, machine_session = _world("related-all")
    reply = _get(w)
    assert reply.status_code == 200, reply.content
    body = reply.json()
    assert body["event"]["event_id"] == event.pk and body["event"]["registration_status"] == "attended"
    assert body["booking"]["booking_id"] == booking.pk and body["booking"]["space_name"] == "Workshop room"
    assert [row["session_id"] for row in body["machine_sessions"]] == [machine_session.pk]
    assert w.member.email not in reply.content.decode()


@pytest.mark.parametrize("off, part", [("events", "event"), ("bookings", "booking")])
def test_a_module_that_is_off_hides_only_its_own_part(off, part):
    w, *_ = _world(f"related-off-{off}")
    w.space.enabled_modules = [key for key in w.space.enabled_modules if key != off]
    w.space.save(update_fields=["enabled_modules"])
    body = _get(w).json()
    assert body[part] is None
    assert [key for key in ("event", "booking") if body[key] is not None] == [
        key for key in ("event", "booking") if key != part]
    assert len(body["machine_sessions"]) == 1


def test_machine_sessions_follow_the_sessions_capability():
    w, *_ = _world("related-no-sessions")
    w.space.enabled_features = [key for key in w.space.enabled_features if key != "machines.sessions"]
    w.space.save(update_fields=["enabled_features"])
    assert _get(w).json()["machine_sessions"] == []


def test_each_part_is_gated_by_its_own_area_authority(monkeypatch):
    w, *_ = _world("related-authority")
    monkeypatch.setattr("apps.events.event_authority.can", lambda *args, **kwargs: False)
    assert _get(w).json()["event"] is None
    monkeypatch.setattr("apps.bookings.booking_authority.can", lambda *args, **kwargs: False)
    assert _get(w).json()["booking"] is None
    monkeypatch.setattr("apps.machines.access.scope_machines_for_actor", lambda actor, queryset: queryset.none())
    body = _get(w).json()
    assert body == {"event": None, "booking": None, "machine_sessions": []}


def test_booking_without_an_arrival_and_other_peoples_sessions_are_not_related():
    w, event, booking, machine_session = _world("related-strangers")
    Booking.objects.filter(pk=booking.pk).update(arrived_at=None)
    stranger = make_member("related-stranger", w.space, membership_role="member", role="requester")
    open_session(w, member=stranger, machine=w.machines[1])
    body = _get(w).json()
    assert body["booking"] is None
    assert [row["session_id"] for row in body["machine_sessions"]] == [machine_session.pk]


def test_not_present_person_and_other_space_staff_are_refused():
    w, *_ = _world("related-refused")
    PresenceSession.objects.filter(account=w.member).update(ended_at=timezone.now())
    assert _get(w).status_code == 404
    other, *_ = _world("related-other")
    outsider = other.staff
    live, *_ = _world("related-live")
    assert _get(live, actor=outsider).status_code in (403, 404)
