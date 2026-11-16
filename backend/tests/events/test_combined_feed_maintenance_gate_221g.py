"""Decision 221(g): `maintenance.calendar_feed` also gates maintenance in the combined feed."""

import pytest
from django.utils import timezone
from icalendar import Calendar

from apps.events.calendar_feed_combined import render_combined_calendar
from apps.maintenance.models import MaintenanceSchedule
from tests.maintenance.helpers import make_machine_setup
from tests.maintenance.l16_helpers import switch

pytestmark = pytest.mark.django_db


def _uids(space, user):
    return [str(event["UID"]) for event in Calendar.from_ical(render_combined_calendar(space, user)).walk("VEVENT")
            if str(event["UID"]).startswith("maintenance-")]


def test_switching_the_maintenance_feed_off_removes_maintenance_from_the_combined_feed():
    space, manager, machine, _ = make_machine_setup("combined-221g")
    switch(space, on=("machines.maintenance", "maintenance.calendar_feed"))
    row = MaintenanceSchedule.objects.create(machine=machine, description="Clean optics", interval_days=30,
                                             next_due=timezone.localdate())
    assert _uids(space, manager) == [f"maintenance-{space.pk}-{row.pk}@spaceworks"]
    switch(space, off=("maintenance.calendar_feed",))
    assert _uids(space, manager) == []
