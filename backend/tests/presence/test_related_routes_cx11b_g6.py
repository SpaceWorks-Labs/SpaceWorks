"""Related is a read with independently gated event/booking/machine projections."""
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.bookings.models import BookableSpace, Booking
from apps.events.models import EventRegistration
from apps.machines.models import Machine, MachineSession, MachineType
from tests.events.checkin_helpers import make_event
from tests.notifications.routes_support_cx11b_g6 import cycle, hidden, world
from tests.presence.routes_support_cx11b_g6 import member, seed

pytestmark = [pytest.mark.django_db, pytest.mark.area_presence]


def neighbours(space, person, row):
    now = timezone.now()
    event = make_event(space)
    event.starts_at, event.ends_at = now - timedelta(minutes=30), now + timedelta(hours=2)
    event.status, event.is_public = "published", True
    event.save()
    registration = EventRegistration.objects.create(event=event, member=person, name="G6 attendee",
        email=person.email, phone="12345678", status="attended")
    row.event_registration, row.status = registration, "attending_event"
    row.save(update_fields=["event_registration", "status"])
    room = BookableSpace.objects.create(makerspace=space, name="G6 arrived room")
    booking = Booking.objects.create(space=room, member=person, name="G6 attendee", email=person.email,
        status="confirmed", starts_at=now - timedelta(minutes=30), ends_at=now + timedelta(hours=1),
        arrived_at=now - timedelta(minutes=4))
    kind = MachineType.objects.create(makerspace=space, name="G6 machine type", slug="g6-type")
    machine = Machine.objects.create(makerspace=space, machine_type=kind, name="G6 public machine", is_public=True)
    session = MachineSession.objects.create(makerspace=space, machine=machine, machine_type=kind,
        member=person, source="staff", started_at=now - timedelta(minutes=3))
    return event, booking, session


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["presence", "events", "bookings", "machines", "machines.sessions"])
def test_related_exact_neighbours_restore_independently_and_hide_foreign_staff(key, native):
    space, actor, client, stranger, foreign = world(native, staff=True)
    person = member(space)
    row, preference, project = seed(space, person)
    event, booking, machine_session = neighbours(space, person, row)
    url = reverse("admin-presence-related", kwargs={"makerspace_id": space.pk, "account_id": person.pk})
    def check(response, missing=None):
        body = response.data
        assert set(body) == {"event", "booking", "machine_sessions"}
        if missing == "events":
            assert body["event"] is None
        else:
            assert (body["event"]["event_id"], body["event"]["title"], body["event"]["registration_status"]) == (
                event.pk, event.title, "attended")
        if missing == "bookings":
            assert body["booking"] is None
        else:
            assert (body["booking"]["booking_id"], body["booking"]["space_name"]) == (booking.pk, "G6 arrived room")
        if missing in {"machines", "machines.sessions"}:
            assert body["machine_sessions"] == []
        else:
            assert [(r["session_id"], r["machine_name"]) for r in body["machine_sessions"]] == [
                (machine_session.pk, "G6 public machine")]
    cycle(space, key, lambda: client.get(url), check,
          off=(404, "not_found") if key == "presence" else (200, None),
          off_check=None if key == "presence" else lambda response: check(response, key),
          probes=[hidden(lambda: foreign.get(url), native_staff=native)])


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
def test_event_presence_renewal_depends_on_live_events_and_caps_at_exact_event_end(native):
    from apps.presence.models import PresenceSession
    from tests.notifications.routes_support_cx11b_g6 import send
    space, person, client, stranger, foreign = world(native)
    row, preference, project = seed(space, person)
    event, booking, machine_session = neighbours(space, person, row)
    url = reverse("presence-renew", kwargs={"makerspace_slug": space.slug})
    def check(response):
        saved = PresenceSession.objects.get(pk=row.pk)
        assert (saved.expires_at, saved.revision, saved.event_registration_id) == (
            event.ends_at, 2, row.event_registration_id)
        assert response.data["status"] == "attending_event" and response.data["active"] is True
    def foreign_call():
        # INVARIANTS identity contract: an account without a session cannot renew someone else's.
        response = send(foreign, "post", url, {"duration_minutes": 240})
        assert response.data["code"] == ("permission_denied" if native else "session_required")
        return response
    cycle(space, "events", lambda: send(client, "post", url, {"duration_minutes": 240}), check,
          off=(400, "event_session"), actions=("presence.renewed",),
          probes=[(foreign_call, (403, "permission_denied") if native else (400, "session_required"),
                   (403, "permission_denied") if native else (400, "session_required"))])
