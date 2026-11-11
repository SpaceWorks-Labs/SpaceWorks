from dataclasses import replace
from datetime import timedelta
from unittest.mock import Mock
import time

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone

from apps.operations.cloud_jobs import contracts, journal, tick_service
from apps.operations.cloud_jobs.catalog import periodic_catalog
from apps.operations.cloud_jobs.contracts import BudgetExpired, ChunkContext, ChunkResult
from apps.operations.cloud_jobs.tick_policy import tick_budget


@pytest.mark.parametrize("value", [-1, 0, 2, 21, 60, True, "20"])
def test_budget_cannot_exceed_warm_request_envelope(settings, value):
    settings.FREE_TICK_BUDGET_SECONDS = value
    with pytest.raises(ImproperlyConfigured):
        tick_budget()


def test_expired_budget_never_enters_provider_fence():
    fence = Mock()
    context = ChunkContext(time.monotonic()-1, fence, {}, None, 1)
    with pytest.raises(BudgetExpired):
        context.check()
    fence.assert_not_called()


def test_context_caps_transport_timeout():
    context = ChunkContext(time.monotonic()+0.5, lambda: None, {}, None, 1)
    assert 0 < context.timeout(5) <= 0.5


@pytest.mark.django_db(transaction=True)
def test_first_tick_runs_critical_work_and_second_tick_observes_due_claims(settings, monkeypatch):
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "free"
    monkeypatch.setattr(contracts, "_admission", lambda: None)
    critical = replace(periodic_catalog()[0], critical=True)
    ordinary = replace(periodic_catalog()[1], critical=False)
    monkeypatch.setattr(tick_service, "periodic_catalog", lambda: (critical, ordinary))
    callback = Mock(return_value=ChunkResult(True))
    monkeypatch.setitem(contracts._chunks, critical.key, callback)
    first, status = tick_service.run_tick()
    assert status == 200
    assert first["completed"] == 1
    second, status = tick_service.run_tick()
    assert status == 200
    assert second["completed"] == 0
    assert callback.call_count == 1
    states = journal.prepare((critical, ordinary))
    assert states[critical.key].last_completed_at is not None
    assert states[ordinary.key].last_completed_at is None
    assert states[ordinary.key].next_due_at > timezone.now()


@pytest.mark.django_db(transaction=True)
def test_failure_is_retryable_and_successful_work_is_not_replayed(settings, monkeypatch):
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "free"
    monkeypatch.setattr(contracts, "_admission", lambda: None)
    tasks = tuple(replace(t, critical=True) for t in periodic_catalog()[:2])
    monkeypatch.setattr(tick_service, "periodic_catalog", lambda: tasks)
    success = Mock(return_value=ChunkResult(True))
    failing = Mock(side_effect=RuntimeError("provider body secret"))
    monkeypatch.setitem(contracts._chunks, tasks[0].key, success)
    monkeypatch.setitem(contracts._chunks, tasks[1].key, failing)
    first, status = tick_service.run_tick()
    assert status == 503
    assert first["completed"] == 1 and first["failed"] == 1
    second, status = tick_service.run_tick()
    assert status == 503
    assert second["reasons"]["operator_reconciliation_required"] == 1
    assert success.call_count == failing.call_count == 1
    assert "secret" not in str(first) + str(second)


@pytest.mark.django_db(transaction=True)
def test_history_retention_expires_finished_detail_only(settings):
    rows = journal.model("CloudTickRun")
    old = timezone.now()-timedelta(days=40)
    complete = rows.objects.create(started_at=old, finished_at=old, status="completed")
    interrupted = rows.objects.create(started_at=old)
    journal.prune_tick_history(days=30)
    assert not rows.objects.filter(pk=complete.pk).exists()
    assert rows.objects.filter(pk=interrupted.pk).exists()
