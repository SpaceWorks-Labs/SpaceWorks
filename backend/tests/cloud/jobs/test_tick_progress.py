from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from threading import Event
import time

import pytest
from django.db import connection, connections
from django.utils import timezone

from apps.operations.cloud_jobs import contracts, journal, tick_locks, tick_service
from apps.operations.cloud_jobs.catalog import periodic_catalog
from apps.operations.cloud_jobs.contracts import ChunkResult, GuardLost
from apps.operations.cloud_jobs.tick_policy import TickRateExceeded, consume_rate

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def task(monkeypatch, settings):
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "free"
    settings.SPACEWORKS_DEPLOYMENT_MODE = "managed"
    monkeypatch.setattr(contracts, "_admission", lambda: None)
    task = replace(periodic_catalog()[0], critical=True)
    journal.prepare((task,))
    return task


def test_partial_chunk_remains_due_and_resumes_exact_checkpoint(task, monkeypatch):
    checkpoints = []

    def chunk(context):
        context.check()
        checkpoints.append(context.checkpoint)
        return ChunkResult(len(checkpoints) == 2, {"after_id": 25}, 25)

    monkeypatch.setitem(contracts._chunks, task.key, chunk)
    assert tick_service._attempt(task, time.monotonic()+15) == ("deferred", "checkpoint_pending")
    row = journal.model("CloudTaskState").objects.get(key=task.key)
    assert row.last_completed_at is None
    assert row.next_due_at <= timezone.now()
    assert tick_service._attempt(task, time.monotonic()+15) == ("completed", "")
    assert checkpoints == [{}, {"after_id": 25}]
    row.refresh_from_db()
    assert row.last_completed_at is not None
    assert row.generation == 2


def test_crash_never_reclaims_running_attempt_by_elapsed_lease(task):
    with tick_locks.task_guard(task.key, 10) as guard:
        row, code = journal.claim(task, guard)
        assert code == ""
    journal.model("CloudTaskState").objects.filter(pk=row.pk).update(last_attempt_at=timezone.now()-timedelta(days=7))
    with tick_locks.task_guard(task.key, 10) as guard:
        claimed, code = journal.claim(task, guard)
        assert claimed is None
        assert code == "operator_reconciliation_required"


def test_guard_excludes_a_contender_during_remote_io(task):
    with tick_locks.task_guard(task.key, 10) as first:
        assert first is not None
        with tick_locks.task_guard(task.key, 10) as contender:
            assert contender is None
        first.check()
    with tick_locks.task_guard(task.key, 10) as replacement:
        assert replacement is not None


def test_killed_guard_fences_old_effect_and_blocks_takeover(task, monkeypatch):
    entered, release = Event(), Event()
    effects, pid = [], []
    original = tick_locks.TaskGuard.acquire

    def acquire(self):
        result = original(self)
        if result and not pid:
            pid.append(self.pid)
        return result

    monkeypatch.setattr(tick_locks.TaskGuard, "acquire", acquire)

    def chunk(context):
        context.check()
        entered.set()
        assert release.wait(5)
        context.check()  # Required fence after provider I/O; no stale commit.
        effects.append("must-never-happen")
        return ChunkResult(True)

    monkeypatch.setitem(contracts._chunks, task.key, chunk)

    takeover = {}

    def kill_and_take_over():
        try:
            assert entered.wait(5)
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_terminate_backend(%s)", [pid[0]])
                takeover["terminated"] = cursor.fetchone()[0]
            # The contender is refused by the durable fence before any deadline/chunk.
            takeover["result"] = tick_service._attempt(task, time.monotonic()+15)
        finally:
            release.set()
            connections.close_all()

    # total_deadline only runs on the main thread (the single-thread free worker),
    # so the old attempt runs here and the killer/contender runs in the helper.
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(kill_and_take_over)
        try:
            old = tick_service._attempt(task, time.monotonic()+15)
        except GuardLost:
            old = ("failed", "fenced")
        future.result(timeout=10)
    assert takeover == {"terminated": True, "result": ("failed", "operator_reconciliation_required")}
    assert old[0] == "failed"
    assert effects == []
    assert journal.model("CloudTaskState").objects.get(key=task.key).status == "uncertain"


def test_rate_limit_is_atomic_across_concurrent_connections(settings):
    settings.FREE_TICK_RATE_LIMIT_PER_MINUTE = 6

    def consume():
        try:
            consume_rate(authenticated=True)
            return True
        except TickRateExceeded:
            return False
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: consume(), range(12)))
    assert sum(results) == 6


def test_missing_bounded_adapter_is_visible_failure(task, monkeypatch):
    monkeypatch.delitem(contracts._chunks, task.key, raising=False)
    assert tick_service._attempt(task, time.monotonic()+15) == ("failed", "bounded_adapter_unavailable")
    row = journal.model("CloudTaskState").objects.get(key=task.key)
    assert row.last_completed_at is None


def test_scheduled_pg_dump_is_refused_before_task_resolution(task):
    disabled = replace(task, free_policy="disabled_in_free_profile")
    assert tick_service._attempt(disabled, time.monotonic()+15) == ("deferred", "disabled_in_free_profile")
    assert journal.model("CloudTaskState").objects.get(key=task.key).status == "disabled"


def test_fairness_rotates_incomplete_work_without_starving_outbox(task):
    other = replace(task, key="another-task", critical=False)
    outbox = replace(task, key="notification-contract-outbox", critical=True)
    states = journal.prepare((task, other, outbox))
    states[task.key].last_attempt_at = timezone.now()
    ordered = tick_service.fair_order((task, other, outbox), states)
    assert ordered[0] == outbox
    assert ordered[1] == other
    assert ordered[-1] == task


def test_managed_full_leader_excludes_overlap_and_fences_connection_loss(task, settings):
    from apps.operations.cloud_jobs.full_scheduler import leader
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    with leader("scheduler") as guard:
        with pytest.raises(GuardLost):
            with leader("scheduler"):
                pytest.fail("A second scheduler entered")
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_terminate_backend(%s)", [guard.pid])
            assert cursor.fetchone()[0]
        with pytest.raises(GuardLost):
            guard.check()
