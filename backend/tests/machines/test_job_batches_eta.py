"""#142 OQ-9 batch runs and OQ-11 attended ETAs over opening hours."""

from datetime import datetime, timedelta, timezone as dt_timezone
from types import SimpleNamespace

import pytest

from apps.machines.models import Machine, MachineServiceRequest
from apps.machines.service_queue_eta import queue_snapshot_for
from apps.machines.service_workflow_batch import complete_batch, start_batch
from apps.makerspaces.opening_hours import advance_open, closing_time
from tests.machines.eta_helpers import NOW, approved, world

pytestmark = pytest.mark.django_db
WEEKDAY_9_TO_17 = {"weekly": {day: [{"start": "09:00", "end": "17:00"}] for day in
                              ("mon", "tue", "wed", "thu", "fri")} | {"sat": [], "sun": []}, "exceptions": {}}


def batched(slug):
    w = world(slug)
    w.space.enabled_features = sorted(set(w.space.enabled_features or []) | {"machines.batch_start"})
    w.space.save(update_fields=["enabled_features"])
    return w


def test_a_batch_shares_one_machine_and_frees_it_with_the_last_job():
    w = batched("batch-run")
    one, two = approved(w, 30, created=-10), approved(w, 10, created=-5)
    batch, started = start_batch([one, two], w.staff, machine_id=w.machines[0].pk)
    assert {row.status for row in started} == {"in_progress"} and {row.batch_id for row in started} == {batch.pk}
    machine = Machine.objects.get(pk=w.machines[0].pk)
    assert machine.status == "running"
    done = complete_batch(batch, w.staff, actual_minutes=80)
    assert sorted(row.actual_minutes for row in done) == [20, 60]  # split 3:1 by estimate
    machine.refresh_from_db()
    batch.refresh_from_db()
    assert machine.status == "idle" and batch.ended_at is not None


def test_batch_start_needs_its_switch_and_two_jobs():
    w = world("batch-off")
    one, two = approved(w, 30, created=-10), approved(w, 10, created=-5)
    with pytest.raises(Exception):
        start_batch([one, two], w.staff, machine_id=w.machines[0].pk)
    with pytest.raises(Exception):
        start_batch([one], w.staff, machine_id=w.machines[0].pk)
    assert MachineServiceRequest.objects.get(pk=one.pk).status == "accepted"


def test_advance_open_skips_closed_hours_and_closing_time_is_reusable():
    space = SimpleNamespace(timezone="UTC", opening_hours=WEEKDAY_9_TO_17)
    friday_4pm = datetime(2026, 10, 16, 16, 0, tzinfo=dt_timezone.utc)
    assert advance_open(space, friday_4pm, 120) == datetime(2026, 10, 19, 10, 0, tzinfo=dt_timezone.utc)
    assert closing_time(space, friday_4pm) == datetime(2026, 10, 16, 17, 0, tzinfo=dt_timezone.utc)
    assert closing_time(space, friday_4pm + timedelta(hours=2)) is None
    always = SimpleNamespace(timezone="UTC", opening_hours={})
    assert advance_open(always, friday_4pm, 120) == friday_4pm + timedelta(hours=2)


def test_attended_job_eta_lands_inside_opening_hours():
    w = world("eta-hours")
    w.space.timezone, w.space.opening_hours = "UTC", WEEKDAY_9_TO_17
    w.space.save(update_fields=["timezone", "opening_hours"])
    row = approved(w, 600, created=-5)  # ten hours of attended work, queued on a Sunday 10:00
    sunday = NOW  # 2026-10-18 is a Sunday
    eta = queue_snapshot_for([row], now=sunday).eta(row)
    assert eta["estimated_start_at"] == datetime(2026, 10, 19, 9, 0, tzinfo=dt_timezone.utc)
    assert eta["estimated_finish_at"] == datetime(2026, 10, 20, 11, 0, tzinfo=dt_timezone.utc)
