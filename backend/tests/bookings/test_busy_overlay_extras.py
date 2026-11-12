"""P3-1 (maintenance in the combined feed) and P3-4 (open-now status in the bootstrap)."""

from datetime import datetime, timedelta, timezone as dt_timezone

import pytest
from django.utils import timezone
from icalendar import Calendar

from apps.events.calendar_feed_combined import render_combined_calendar
from apps.maintenance.models import MaintenanceSchedule
from apps.makerspaces.open_status import open_status
from apps.makerspaces.platform import bootstrap_payload
from tests.maintenance.helpers import make_machine_setup
from tests.maintenance.l16_helpers import switch
from tests.return_helpers import make_member

pytestmark = pytest.mark.django_db


def maintenance_uids(space, user):
    return [str(event["UID"]) for event in Calendar.from_ical(render_combined_calendar(space, user)).walk("VEVENT")
            if str(event["UID"]).startswith("maintenance-")]


def test_combined_feed_carries_maintenance_only_for_machine_scope_and_the_capability():
    space, manager, machine, _ = make_machine_setup("busy-p31")
    switch(space, on=("machines.maintenance", "maintenance.calendar_feed"))  # decision 221(g)
    row = MaintenanceSchedule.objects.create(machine=machine, description="Clean optics", interval_days=30,
                                             next_due=timezone.localdate())
    member = make_member("busy-p31-member", space, membership_role="custom", role="requester")
    assert maintenance_uids(space, manager) == [f"maintenance-{space.pk}-{row.pk}@spaceworks"]
    assert maintenance_uids(space, member) == []
    switch(space, off=("machines.maintenance",))
    assert maintenance_uids(space, manager) == []


class Hours:
    timezone = "UTC"

    def __init__(self, hours):
        self.opening_hours = hours


def at(hour, day=12):
    return datetime(2026, 11, day, hour, tzinfo=dt_timezone.utc)  # 2026-11-12 is a Thursday


def test_open_status_open_closed_and_joined_midnight_openings():
    hours = Hours({"weekly": {"thu": [{"start": "09:00", "end": "17:00"}], "fri": [{"start": "09:00", "end": "17:00"}]}})
    assert open_status(hours, at(10)) == {"open_now": True, "closes_at": at(17).isoformat(), "next_opens_at": None}
    assert open_status(hours, at(18)) == {"open_now": False, "closes_at": None, "next_opens_at": at(9, 13).isoformat()}
    late = Hours({"weekly": {"thu": [{"start": "20:00", "end": "24:00"}], "fri": [{"start": "00:00", "end": "02:00"}]}})
    assert open_status(late, at(21))["closes_at"] == datetime(2026, 11, 13, 2, tzinfo=dt_timezone.utc).isoformat()


def test_bootstrap_open_status_only_when_hours_are_recorded():
    space, _, _, _ = make_machine_setup("busy-p34")
    space.opening_hours = {}
    space.save(update_fields=["opening_hours"])
    assert "open_status" not in bootstrap_payload(space)["makerspace"]
    space.opening_hours = {"weekly": {day: [{"start": "00:00", "end": "24:00"}]
                                      for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}}
    space.save(update_fields=["opening_hours"])
    assert bootstrap_payload(space)["makerspace"]["open_status"]["open_now"] is True
