"""Unified busy overlay (P1-3, P3-1, P3-4): outages, repairs and closures, read-only."""

from datetime import datetime, timedelta, timezone as dt_timezone

import pytest
from django.urls import reverse
from django.utils import timezone
from icalendar import Calendar
from rest_framework.test import APIClient

from apps.bookings.busy_overlay import busy_blocks
from apps.bookings.models import BookableSpace
from apps.machines.models import Machine
from apps.maintenance.models import RoomOutage
from tests.bookings.test_member_booking_api import book, setup as _setup
from tests.maintenance.l16_helpers import switch

pytestmark = pytest.mark.django_db


def setup(slug, *args, **kwargs):
    """The outage layer sits behind `bookings.room_maintenance` (module on/off audit, 0.12.0)."""
    result = _setup(slug, *args, **kwargs)
    switch(result[1].makerspace, on=("bookings.room_maintenance",))
    return result


def outage(room, *, mode="block", reason="Flooded basement", days=3):
    return RoomOutage.objects.create(makerspace=room.makerspace, room=room, mode=mode, reason=reason,
                                     started_at=timezone.now(), expected_back_at=timezone.now() + timedelta(days=days))


def window(days=7):
    start = timezone.now()
    return start, start + timedelta(days=days)


def test_staff_see_kind_severity_and_reason_public_sees_bare_unavailable_and_no_warn_outage():
    _, room, _, _ = setup("busy-kinds")
    outage(room)
    start, end = window()
    staff = busy_blocks(room, start, end, staff=True)
    assert [(row["kind"], row["severity"], row["reason"]) for row in staff] == [("room_outage", "block", "Flooded basement")]
    assert busy_blocks(room, start, end, staff=False) == [
        {"starts_at": staff[0]["starts_at"], "ends_at": staff[0]["ends_at"], "kind": "unavailable"}]
    RoomOutage.objects.filter(room=room).update(mode="warn")
    assert busy_blocks(room, start, end, staff=True)[0]["severity"] == "warn"
    assert busy_blocks(room, start, end, staff=False) == []


def test_an_open_ended_outage_is_clipped_to_the_window():
    _, room, _, _ = setup("busy-clip")
    RoomOutage.objects.create(makerspace=room.makerspace, room=room, started_at=timezone.now() - timedelta(days=9))
    start, end = window(2)
    [row] = busy_blocks(room, start, end, staff=True)
    assert (row["starts_at"], row["ends_at"]) == (start, end)


def test_maintenance_tombstoned_removes_the_outage_layer(monkeypatch):
    _, room, _, _ = setup("busy-tomb")
    outage(room)
    from apps.separability import registry
    real = registry.runtime_active
    monkeypatch.setattr(registry, "runtime_active", lambda label: label != "maintenance" and real(label))
    assert busy_blocks(room, *window(), staff=True) == []


def test_machine_repair_reads_as_unavailable_to_the_public():
    from apps.machines.models import MachineType
    tenant, room, _, _ = setup("busy-repair")
    kind = MachineType.objects.create(makerspace=tenant, slug="busy-laser", name="Laser")
    machine = Machine.objects.create(makerspace=tenant, machine_type=kind, name="Laser A")
    BookableSpace.objects.filter(pk=room.pk).update(machine=machine)
    room.refresh_from_db()
    switch(tenant, on=("machines.time_booking",))  # decision 230 (d): a machine-linked room books only while on
    start, end = window(1)
    assert busy_blocks(room, start, end, staff=True) == []
    Machine.objects.filter(pk=machine.pk).update(status="maintenance")
    assert [row["kind"] for row in busy_blocks(room, start, end, staff=True)] == ["machine_repair"]
    assert [row["kind"] for row in busy_blocks(room, start, end, staff=False)] == ["unavailable"]


def test_closures_are_the_gaps_in_recorded_hours_and_absent_without_hours():
    tenant, room, _, _ = setup("busy-hours")
    day = (timezone.now() + timedelta(days=3)).date()
    lo = datetime.combine(day, datetime.min.time(), tzinfo=dt_timezone.utc)
    hi = lo + timedelta(days=1)
    assert busy_blocks(room, lo, hi, staff=True) == []
    tenant.timezone = "UTC"
    tenant.opening_hours = {"weekly": {}, "exceptions": {day.isoformat(): [{"start": "09:00", "end": "17:00"}]}}
    tenant.save(update_fields=["timezone", "opening_hours"])
    room.refresh_from_db()
    closed = busy_blocks(room, lo, hi, staff=False)
    assert [(row["kind"], row["starts_at"].hour, row["ends_at"]) for row in closed] == [
        ("closed", 0, lo + timedelta(hours=9)), ("closed", 17, hi)]
    assert busy_blocks(room, lo, hi, staff=False, closures=False) == []


def test_public_availability_carries_bare_blocks_and_never_the_reason():
    tenant, room, _, _ = setup("busy-public", is_public=True, show_public_availability=True)
    outage(room, reason="Asbestos survey")
    start, end = window()
    response = APIClient().get(reverse("public-space-availability", kwargs={
        "makerspace_slug": tenant.slug, "public_token": room.public_token,
    }), {"starts_at": start.isoformat(), "ends_at": end.isoformat()})
    assert response.status_code == 200
    assert [row["kind"] for row in response.data["unavailable"]] == ["unavailable"]
    assert b"Asbestos" not in response.content and b"room_outage" not in response.content


def test_public_availability_hides_outages_when_the_room_does_not_publish_availability():
    # Decision 219c: the bare `unavailable` follows the room's public-availability setting;
    # `closed` (the published opening hours) still shows.
    tenant, room, _, _ = setup("busy-public-off", is_public=True)
    outage(room, reason="Asbestos survey")
    day = (timezone.now() + timedelta(days=1)).date()
    tenant.timezone = "UTC"
    tenant.opening_hours = {"weekly": {}, "exceptions": {day.isoformat(): [{"start": "09:00", "end": "17:00"}]}}
    tenant.save(update_fields=["timezone", "opening_hours"])
    start, end = window()
    response = APIClient().get(reverse("public-space-availability", kwargs={
        "makerspace_slug": tenant.slug, "public_token": room.public_token,
    }), {"starts_at": start.isoformat(), "ends_at": end.isoformat()})
    assert response.status_code == 200
    assert response.data["availability"] is None
    kinds = {row["kind"] for row in response.data["unavailable"]}
    assert kinds == {"closed"}
    assert b"Asbestos" not in response.content and b"room_outage" not in response.content


def test_member_feed_marks_only_outages_that_meet_their_own_upcoming_booking():
    tenant, room, user, client = setup("busy-feed")
    other_room = BookableSpace.objects.create(makerspace=tenant, name="Other", approval_mode="instant")
    mine = book(room, user)
    outage(other_room, reason="Other room secret")
    url = client.post(reverse("member-booking-feed-settings", kwargs={"makerspace_slug": tenant.slug}),
                      {}, format="json").data["feed_url"]
    events = Calendar.from_ical(APIClient().get(url).content).walk("VEVENT")
    assert [str(event["UID"]) for event in events] == [f"booking-{mine.public_token}@spaceworks"]
    outage(room, reason="Flooded basement")
    response = APIClient().get(url)
    busy = [event for event in Calendar.from_ical(response.content).walk("VEVENT")
            if str(event["UID"]).startswith("busy-")]
    assert len(busy) == 1 and str(busy[0]["TRANSP"]) == "OPAQUE" and str(busy[0]["SUMMARY"]) == "Unavailable"
    assert busy[0]["DTSTART"].dt == mine.starts_at.replace(microsecond=0)
    assert b"Flooded" not in response.content and b"Other room secret" not in response.content


def test_staff_availability_lists_outage_detail():
    from tests.return_helpers import make_member
    tenant, room, _, _ = setup("busy-staff")
    manager = make_member("busy-staff-sm", tenant)
    outage(room, mode="warn", reason="Leaky roof")
    client = APIClient()
    client.force_authenticate(manager)
    start, end = window(2)
    response = client.get(reverse("admin-space-booking-availability", kwargs={"pk": room.pk}),
                          {"starts_at": start.isoformat(), "ends_at": end.isoformat()})
    assert response.status_code == 200
    [row] = [row for row in response.data["unavailable"] if row["kind"] == "room_outage"]
    assert (row["severity"], row["reason"]) == ("warn", "Leaky roof")


def test_event_venue_shows_only_a_neutral_update_pending_flag_during_the_event():
    from apps.events.models import Event
    tenant, room, _, _ = setup("busy-venue", is_public=True)
    tenant.enabled_modules = sorted(set(tenant.enabled_modules or []) | {"events"})
    tenant.save(update_fields=["enabled_modules"])
    start = timezone.now() + timedelta(days=1)
    event = Event.objects.create(makerspace=tenant, title="Bootcamp", starts_at=start, ends_at=start + timedelta(hours=2),
                                 location="Room", is_public=True, status=Event.Status.PUBLISHED)
    url = reverse("public-event-venue", kwargs={"makerspace_slug": tenant.slug, "public_token": event.public_token})
    assert APIClient().get(url).json()["space"]["venue_update_pending"] is False
    outage(room, reason="Flooded basement")
    response = APIClient().get(url)
    space = response.json()["space"]
    # Decision 219c: a neutral flag only -- no blocks, windows or reasons on the public event page.
    assert space["venue_update_pending"] is True and "unavailable" not in space
    assert set(space) == {"public_token", "name", "kind", "location", "capacity", "venue_update_pending"}
    assert b"Flooded" not in response.content and b"starts_at" not in response.content
