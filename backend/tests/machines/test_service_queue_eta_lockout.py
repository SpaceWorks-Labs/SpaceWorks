"""Queue ETAs honour maintenance lockout (machines D6) through `lockout.schedule_blocks`."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.machines.lockout import blocking_schedules
from apps.machines.models import MachineServiceRequest, MachineUsageEntry, MakerspaceMachineTypePolicy
from apps.machines.service_queue_eta import machine_queue_summaries_for, queue_snapshot_for
from apps.maintenance.models import MaintenanceSchedule
from tests.machines.eta_helpers import NOW, approved, world

pytestmark = pytest.mark.django_db

TODAY = timezone.localdate(NOW)
LOCKED = {"length": 0, "eta_minutes": None, "estimated_clear_at": None, "calculated_at": NOW,
          "confidence": "unavailable", "reasons": ["no_active_machine"]}
FREE = {"length": 0, "eta_minutes": 0, "estimated_clear_at": NOW, "calculated_at": NOW,
        "confidence": "estimated", "reasons": []}


def features(w, *on, off=()):
    w.space.enabled_features = sorted((set(w.space.enabled_features or []) | set(on)) - set(off))
    w.space.save(update_fields=["enabled_features"])


def maintained(slug, *, meters=False, machines=2):
    w = world(slug, machines=machines)
    features(w, "machines.maintenance", *(["maintenance.meters"] if meters else []))
    return w


def overdue(machine, days=1, **kwargs):
    return MaintenanceSchedule.objects.create(machine=machine, description="Laser alignment", interval_days=30,
                                              next_due=TODAY - timedelta(days=days), blocks_use=True, **kwargs)


def summaries(w):
    found = machine_queue_summaries_for(w.machines, now=NOW)
    return [found[machine.pk] for machine in w.machines]


def test_time_lockout_withholds_the_machine_and_agrees_with_the_start_gate():
    w = maintained("eta-lock-time")
    a, b = w.machines
    overdue(a)
    MaintenanceSchedule.objects.create(machine=b, description="Not blocking", interval_days=30,
                                       next_due=TODAY - timedelta(days=9), blocks_use=False)
    assert blocking_schedules(a, today=TODAY) and not blocking_schedules(b, today=TODAY)
    assert summaries(w) == [LOCKED, FREE]


def test_a_locked_only_machine_leaves_queued_work_unavailable():
    w = maintained("eta-lock-job", machines=1)
    overdue(w.machines[0])
    row = approved(w, 10, created=-5)
    eta = queue_snapshot_for([row], now=NOW).eta(row)
    assert eta["confidence"] == "unavailable" and eta["start_in_minutes"] is None
    assert "no_active_machine" in eta["reasons"] and eta["active_machine_count"] == 0


def test_within_grace_the_machine_stays_available():
    w = maintained("eta-lock-grace")
    a, _ = w.machines
    overdue(a, days=2)
    MakerspaceMachineTypePolicy.objects.create(makerspace=w.space, machine_type=w.kind, grace_days=3)
    assert not blocking_schedules(a, today=TODAY)
    assert summaries(w) == [FREE, FREE]
    MakerspaceMachineTypePolicy.objects.filter(makerspace=w.space, machine_type=w.kind).update(grace_days=2)
    assert blocking_schedules(a, today=TODAY)
    assert summaries(w) == [LOCKED, FREE]


def test_meter_lockout_blocks_once_the_usage_threshold_is_reached():
    w = maintained("eta-lock-meter", meters=True)
    a, b = w.machines
    overdue(a, days=-30, trigger="usage", usage_hours=Decimal("2"))
    overdue(b, days=-30, trigger="both", job_count=2)
    MachineUsageEntry.objects.create(machine=a, hours=Decimal("1.50"))
    MachineUsageEntry.objects.create(machine=b, source=MachineUsageEntry.Source.TYPED_MANUAL, hours=1)
    assert summaries(w) == [FREE, FREE]
    MachineUsageEntry.objects.create(machine=a, hours=Decimal("0.50"))
    MachineUsageEntry.objects.create(machine=b, source=MachineUsageEntry.Source.TYPED_MANUAL, hours=1)
    assert blocking_schedules(a, today=TODAY) and blocking_schedules(b, today=TODAY)
    assert summaries(w) == [LOCKED, LOCKED]
    features(w, off=("maintenance.meters",))
    assert not blocking_schedules(a, today=TODAY)
    assert summaries(w) == [FREE, FREE]


def test_maintenance_switch_off_means_no_lockout():
    w = world("eta-lock-off")
    features(w, off=("machines.maintenance",))
    overdue(w.machines[0], days=10)
    assert not blocking_schedules(w.machines[0], today=TODAY)
    assert summaries(w) == [FREE, FREE]


def test_lockout_keeps_the_four_query_budget():
    w = maintained("eta-lock-budget", meters=True, machines=4)
    for machine in w.machines[:2]:
        overdue(machine)
    overdue(w.machines[2], days=-30, trigger="usage", usage_hours=Decimal("1"))
    MachineUsageEntry.objects.create(machine=w.machines[2], hours=Decimal("3"))
    rows = [approved(w, 5, created=-i) for i in range(6)]
    targets = list(MachineServiceRequest.objects.filter(pk__in=[row.pk for row in rows]))
    with CaptureQueriesContext(connection) as captured:
        snapshot = queue_snapshot_for(targets, machines=w.machines, now=NOW)
        [snapshot.eta(row) for row in targets]
        found = [snapshot.machine_summary(machine) for machine in w.machines]
    assert len(captured.captured_queries) <= 4
    assert [item["confidence"] for item in found[:3]] == ["unavailable"] * 3
    assert found[3]["confidence"] != "unavailable"
