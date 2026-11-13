"""Decision 220(d)3: a Technician gets the maintenance calendar feed for the machine types
their in-house contact covers -- only those machines, and nothing without coverage."""

import pytest
from django.urls import reverse
from django.utils import timezone
from icalendar import Calendar
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient

from apps.maintenance.calendar_feed import feed_space, issue
from apps.maintenance.models import MaintenanceSchedule, TechnicianCoverage
from tests.maintenance.l16_helpers import in_house, switch, world

pytestmark = pytest.mark.django_db


def _world(slug):
    w = world(slug)
    switch(w.space, on=("maintenance.calendar_feed",))
    for machine in (w.machine, w.other):
        MaintenanceSchedule.objects.create(machine=machine, description="Check", interval_days=30,
                                           next_due=timezone.localdate())
    return w


def test_covering_technician_reads_only_the_covered_machine_types():
    w = _world("feed-tech")
    in_house(w, coverage=[{"kind": "machine_type", "machine_type": w.kind}])
    _, token = issue(w.tech, w.space)
    url = reverse("maintenance-feed-calendar", kwargs={"makerspace_id": w.space.pk, "raw_token": token})
    response = APIClient().get(url)
    assert response.status_code == 200
    summaries = [str(event["SUMMARY"]) for event in Calendar.from_ical(response.content).walk("VEVENT")]
    assert summaries == ["Laser A: maintenance"]
    # Coverage withdrawn: the bearer feed rechecks the person's scope on every read.
    TechnicianCoverage.objects.filter(contact__person=w.tech).delete()
    assert APIClient().get(url).status_code == 404


def test_technician_without_coverage_or_with_room_coverage_gets_no_feed():
    w = _world("feed-tech-none")
    with pytest.raises(PermissionDenied):
        feed_space(w.tech, w.space.pk)
    in_house(w, coverage=[{"kind": "room", "room": w.room}])
    with pytest.raises(PermissionDenied):
        feed_space(w.tech, w.space.pk)


def test_machine_maintenance_switched_off_drops_coverage():
    w = _world("feed-tech-off")
    in_house(w, coverage=[{"kind": "machine_type", "machine_type": w.kind}])
    assert feed_space(w.tech, w.space.pk) == w.space
    switch(w.space, off=("machines.maintenance",))
    with pytest.raises(Exception):
        feed_space(w.tech, w.space.pk)
