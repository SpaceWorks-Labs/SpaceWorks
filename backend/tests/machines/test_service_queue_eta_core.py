"""Pure, deterministic tests for the queue simulator (no database)."""

from datetime import datetime, timedelta, timezone as dt_timezone

import pytest

from apps.machines.service_queue_eta_core import (
    JobRecord, MachineRecord, ScopeRecord, Timeline, lane_summary, project, round_up,
)

NOW = datetime(2026, 10, 18, 10, 0, tzinfo=dt_timezone.utc)
G = (1, 7)
Q = ("queue", 1)


def m(mid, status="idle", active=True, group=G):
    return MachineRecord(mid, group, active, status)


def run(jid, minutes, started_ago, machine, scope=Q):
    started = None if started_ago is None else NOW - timedelta(minutes=started_ago)
    return JobRecord(jid, scope, "in_progress", NOW - timedelta(hours=3), minutes, started_at=started, machine_id=machine)


def wait(jid, minutes, created, status="accepted", scope=Q):
    return JobRecord(jid, scope, status, NOW + timedelta(minutes=created), minutes)


def tl(machines, running=(), waiting=(), scopes=None, probes=()):
    scopes = scopes or [ScopeRecord(Q, G, True)]
    return Timeline(NOW, machines, scopes, running, waiting, probe_ids=probes)


def eta(timeline, jid):
    return project(NOW, timeline.forecasts[jid])


def window(timeline, jid):
    value = eta(timeline, jid)
    return value["start_in_minutes"], value["finish_in_minutes"], value["confidence"]


def owner_case(**changes):
    machines = [m(1, "running"), m(2, "running")]
    running = [run(10, 20, 10, 1), run(11, 40, 10, 2)]
    waiting = [wait(20, 60, -50), wait(21, 20, -40), wait(22, 15, -30), wait(23, 900, -35, "pending")]
    return machines, running, waiting


def test_owner_multi_printer_regression_simulates_parallel_machines_not_a_sum():
    machines, running, waiting = owner_case()
    t = tl(machines, running, waiting, probes=[23])
    assert window(t, 20) == (10, 70, "estimated")   # predecessor 1 on A 10:10-11:10
    assert window(t, 21) == (30, 50, "estimated")   # predecessor 2 on B 10:30-10:50
    target = eta(t, 22)
    assert (target["start_in_minutes"], target["finish_in_minutes"]) == (50, 65)
    assert target["estimated_start_at"] == NOW + timedelta(minutes=50)
    assert target["estimated_finish_at"] == NOW + timedelta(minutes=65)
    assert target["confidence"] == "estimated" and target["reasons"] == []
    # A 900-minute pending job adds no load and is only probed (rough, if approved).
    assert eta(t, 23)["confidence"] == "rough" and "awaiting_approval" in eta(t, 23)["reasons"]
    assert t.facts(waiting[2]) == {"position": 3, "approved_ahead": 2, "awaiting_review_ahead": 0,
                                   "active_machine_count": 2, "missing_estimate_count": 0}


def test_cancelling_waiting_or_running_work_shortens_the_timeline():
    machines, running, waiting = owner_case()
    without_second = tl(machines, running, [w for w in waiting if w.id != 21])
    assert window(without_second, 22)[:2] == (30, 45)
    # Cancelling a running job releases its machine to idle in the same transaction.
    without_running_b = tl([m(1, "running"), m(2)], [running[0]], waiting)
    assert window(without_running_b, 20)[:2] == (0, 60)    # B 10:00-11:00
    assert window(without_running_b, 21)[:2] == (10, 30)   # A 10:10-10:30
    assert window(without_running_b, 22)[:2] == (30, 45)   # A 10:30-10:45


def test_bucket_jobs_wait_for_their_own_machine_even_when_another_is_idle():
    bucket = ("bucket", 5)
    scopes = [ScopeRecord(bucket, G, True, machine_id=1), ScopeRecord(Q, G, True)]
    t = tl([m(1, "running"), m(2)], [run(10, 30, 0, 1, scope=bucket)], [wait(20, 10, -5, scope=bucket)], scopes=scopes)
    assert window(t, 20)[:2] == (30, 40)


def test_idle_machines_run_in_parallel_and_ties_break_on_machine_id():
    t = tl([m(2), m(1)], (), [wait(20, 30, -2), wait(21, 30, -1), wait(22, 10, 0)])
    assert window(t, 20)[:2] == (0, 30) and window(t, 21)[:2] == (0, 30)
    assert t.lanes[1].length == 2 and t.lanes[2].length == 1  # the third tie went to machine 1


def test_accepted_first_and_pending_never_consume_simulated_time():
    waiting = [wait(30, 600, -100, "pending"), wait(31, 10, -5)]
    t = tl([m(1)], (), waiting, probes=[30])
    assert window(t, 31)[:2] == (0, 10)
    assert t.facts(waiting[1])["position"] == 1 and t.facts(waiting[0])["approved_ahead"] == 1
    assert window(t, 30) == (10, 610, "rough")


def test_missing_estimates_are_unavailable_and_never_zero():
    t = tl([m(1)], (), [wait(20, None, -2), wait(21, 10, -1)])
    for jid in (20, 21):
        value = eta(t, jid)
        assert value["confidence"] == "unavailable" and value["start_in_minutes"] is None
        assert value["estimated_finish_at"] is None and "missing_estimate" in value["reasons"]
    assert t.facts(wait(21, 10, -1))["missing_estimate_count"] == 1


def test_a_later_missing_estimate_does_not_taint_earlier_requests():
    t = tl([m(1)], (), [wait(20, 10, -3), wait(21, 15, -2), wait(22, None, -1)])
    assert window(t, 20) == (0, 10, "estimated") and window(t, 21) == (10, 25, "estimated")


def test_unknown_running_state_withholds_dependent_forecasts():
    no_row = tl([m(1, "running")], (), [wait(20, 10, -1)])
    assert eta(no_row, 20)["reasons"] == ["unknown_running_job"]
    duplicate = tl([m(1, "running")], [run(10, 10, 1, 1), run(11, 10, 1, 1)], [wait(20, 10, -1)])
    assert eta(duplicate, 20)["confidence"] == "unavailable"
    no_start = tl([m(1, "running")], [run(10, 10, None, 1)], [wait(20, 10, -1)])
    assert eta(no_start, 20)["confidence"] == "unavailable"
    assert eta(no_start, 10)["reasons"] == ["unknown_running_job"]


def test_overdue_running_jobs_floor_to_five_minutes_and_read_rough():
    t = tl([m(1, "running")], [run(10, 20, 45, 1)], [wait(20, 10, -1)])
    assert window(t, 20) == (5, 15, "rough")
    assert "overdue_running_job" in eta(t, 20)["reasons"]
    assert eta(t, 10)["finish_in_minutes"] == 5 and eta(t, 10)["start_in_minutes"] == 0


def test_a_coherent_running_row_governs_availability_whatever_the_flag_says():
    t = tl([m(1, "idle")], [run(10, 30, 0, 1)], [wait(20, 10, -1)])
    assert window(t, 20)[:2] == (30, 40)


@pytest.mark.parametrize("status,active", [("reserved", True), ("maintenance", True), ("offline", True), ("idle", False)])
def test_excluded_machines_give_no_capacity(status, active):
    t = tl([m(1, status, active)], (), [wait(20, 10, -1)])
    value = eta(t, 20)
    assert value["confidence"] == "unavailable" and value["reasons"] == ["no_active_machine"]
    assert lane_summary(NOW, t, 1)["eta_minutes"] is None


def test_unrelated_types_and_tenants_never_share_capacity():
    other = (2, 7)
    scopes = [ScopeRecord(Q, G, True), ScopeRecord(("queue", 2), other, True)]
    t = tl([m(1, group=other)], (), [wait(20, 10, -1)], scopes=scopes)
    assert eta(t, 20)["reasons"] == ["no_active_machine"]


def test_shared_scopes_interleave_without_double_allocation_and_read_rough():
    bucket = ("bucket", 9)
    scopes = [ScopeRecord(Q, G, True), ScopeRecord(bucket, G, True, machine_id=1)]
    waiting = [wait(20, 30, -3), wait(21, 30, -2, scope=bucket), wait(22, 10, -1)]
    t = tl([m(1)], (), waiting, scopes=scopes)
    assert window(t, 20)[:2] == (0, 30)
    assert window(t, 21) == (30, 60, "rough") and "competing_scopes" in eta(t, 21)["reasons"]
    assert window(t, 22)[:2] == (60, 70)


def test_queue_capacity_limits_concurrency_beyond_free_machines():
    scopes = [ScopeRecord(Q, G, True, capacity=1)]
    t = tl([m(1), m(2)], (), [wait(20, 30, -2), wait(21, 30, -1)], scopes=scopes)
    assert window(t, 20)[:2] == (0, 30) and window(t, 21)[:2] == (30, 60)


@pytest.mark.parametrize("machine_id,status", [(3, "offline"), (3, "maintenance"), (None, "idle")])
def test_capacity_one_slot_held_by_a_job_on_an_excluded_or_unassigned_machine(machine_id, status):
    scopes = [ScopeRecord(Q, G, True, capacity=1)]
    machines = [m(1), m(3, status)]
    t = tl(machines, [run(10, 30, 10, machine_id)], [wait(20, 10, -1)], scopes=scopes)
    assert window(t, 20)[:2] == (20, 30)  # never "now": the running job still holds the slot
    unknown = tl(machines, [run(10, None, 10, machine_id)], [wait(20, 10, -1)], scopes=scopes)
    assert eta(unknown, 20)["confidence"] == "unavailable"


def test_inactive_scope_is_unavailable_without_occupying_machines():
    scopes = [ScopeRecord(Q, G, False), ScopeRecord(("queue", 2), G, True)]
    t = tl([m(1)], (), [wait(20, 10, -2), wait(21, 10, -1, scope=("queue", 2))], scopes=scopes)
    assert eta(t, 20)["reasons"] == ["inactive_scope"]
    assert window(t, 21)[:2] == (0, 10)


def test_in_progress_uses_actual_start_and_rounds_finish_up():
    t = tl([m(1, "running")], [run(10, 20, 7, 1)], ())
    value = eta(t, 10)
    assert value["estimated_start_at"] == NOW - timedelta(minutes=7) and value["start_in_minutes"] == 0
    assert value["finish_in_minutes"] == 15 and value["estimated_finish_at"] == NOW + timedelta(minutes=15)


def test_rounding_is_up_to_five_minutes_and_timestamps_match_minutes():
    assert [round_up(x) for x in (0, 0.01, 4.99, 5, 7.2, 59.5)] == [0, 5, 5, 5, 10, 60]
    t = tl([m(1, "running")], [run(10, 20, 12.8, 1)], [wait(20, 11, -1)])
    value = eta(t, 20)
    assert (value["start_in_minutes"], value["finish_in_minutes"]) == (10, 20)
    assert value["estimated_finish_at"] - value["calculated_at"] == timedelta(minutes=value["finish_in_minutes"])


def test_idle_machine_with_no_work_clears_now_and_summary_reports_final_free_at():
    t = tl([m(1), m(2, "running")], [run(10, 40, 10, 2)], [wait(20, 15, -1)])
    assert lane_summary(NOW, t, 1) | {"calculated_at": None} == {
        "calculated_at": None, "length": 1, "eta_minutes": 15, "estimated_clear_at": NOW + timedelta(minutes=15),
        "confidence": "estimated", "reasons": []}
    assert lane_summary(NOW, t, 2)["eta_minutes"] == 30
    assert lane_summary(NOW, tl([m(5)]), 5)["eta_minutes"] == 0


def test_terminal_rows_have_no_forecast():
    t = tl([m(1)], (), ())
    assert 99 not in t.forecasts
