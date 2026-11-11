from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from apps.operations.cloud_jobs.catalog import LEGACY_ENTRIES, periodic_catalog, provider_inventory
from apps.operations.models_scheduling import PeriodicTaskRun


def test_inventory_preserves_legacy_intervals_and_has_no_duplicate_hooks(settings):
    settings.CLOUD_PROGRAMMES = ()
    settings.TOMBSTONED_APPS = ()
    catalog = periodic_catalog()
    assert {(t.key, t.path, t.minutes) for t in catalog} == set(LEGACY_ENTRIES)
    assert len({t.key for t in catalog}) == len(catalog)
    assert all(row["writer"] == "cron" for row in provider_inventory())


def test_retained_cleanup_survives_tombstone_without_runtime_imports():
    catalog = periodic_catalog(programmes=("events", "reimbursement"), tombstones=("events", "event_reimbursements"))
    keys = {t.key for t in catalog}
    # The merged events programme runs its own retention tasks as legacy entries; a
    # programme wrapper with the same task path (finance-retention) is not declared twice.
    assert {"event-asset-work", "event-asset-lifecycle", "event-print-cleanup", "finance-event-payout-retention"} <= keys
    assert "finance-retention" not in keys
    assert "event-certificate-resume" not in keys
    assert "event-scheduled-broadcasts" not in keys
    assert "stage-form-reconcile" not in keys


def test_stage_retention_has_one_owner_and_admission_is_independent():
    catalog = periodic_catalog(programmes=("events", "reimbursement"), tombstones=())
    assert len([t for t in catalog if t.key == "stage-file-retention"]) == 1
    assert len([t for t in catalog if t.path.endswith("sweep_admission_deadlines_task")]) == 1


@pytest.mark.django_db(transaction=True)
def test_cli_runs_unrelated_tasks_and_records_failure_without_failing_host_pass(monkeypatch, settings):
    # Owner decision #42: a host (full-server) pass keeps its original contract --
    # failures are recorded per task and the command exits 0 (tests/test_scheduled_tasks.py).
    # Only a managed one-off provider job reports them through its exit status.
    from apps.operations.management.commands import run_scheduled_tasks as command
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    settings.SPACEWORKS_DEPLOYMENT_MODE = "host"
    selected = command.SCHEDULED_TASKS[:2]
    monkeypatch.setattr(command, "SCHEDULED_TASKS", selected)
    calls = []

    def resolve(path):
        def run():
            from django.db import connection
            assert not connection.in_atomic_block
            calls.append(path)
            if len(calls) == 1:
                raise RuntimeError("secret should not appear")
        return run

    monkeypatch.setattr(command, "_import_task", resolve)
    out, err = StringIO(), StringIO()
    call_command("run_scheduled_tasks", stdout=out, stderr=err)
    assert calls == [row[1] for row in selected]
    assert "secret" not in err.getvalue()
    assert PeriodicTaskRun.objects.get(name=selected[0][0]).last_error == "RuntimeError"


@pytest.mark.django_db(transaction=True)
def test_full_defaults_preserve_warmup_and_ignore_free_settings(settings, monkeypatch):
    from apps.operations.management.commands import run_scheduled_tasks as command
    settings.SPACEWORKS_DEPLOYMENT_MODE = "host"
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    settings.FREE_TICK_SECRET = "present-but-inert"
    settings.FREE_TICK_BUDGET_SECONDS = -1
    settings.FREE_EMAIL_DAILY_CAP = 0
    monkeypatch.setattr(command, "SCHEDULED_TASKS", command.SCHEDULED_TASKS[:1])
    calls = []
    monkeypatch.setattr(command, "_import_task", lambda path: lambda: calls.append(path))
    call_command("run_scheduled_tasks", due_only=True, stdout=StringIO())
    assert not calls
    PeriodicTaskRun.objects.update(last_run_at=timezone.now()-timedelta(days=1))
    call_command("run_scheduled_tasks", due_only=True, stdout=StringIO())
    assert len(calls) == 1


def test_free_cli_cannot_start_a_resident_scheduler(settings):
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "free"
    with pytest.raises(CommandError, match="authenticated bounded tick"):
        call_command("run_scheduled_tasks", due_only=True, stdout=StringIO())


@pytest.mark.django_db(transaction=True)
def test_reported_domain_failures_are_recorded_not_successful(monkeypatch, settings):
    from apps.operations.management.commands import run_scheduled_tasks as command
    settings.SPACEWORKS_DEPLOYMENT_MODE = "host"
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    monkeypatch.setattr(command, "SCHEDULED_TASKS", command.SCHEDULED_TASKS[:1])
    monkeypatch.setattr(command, "_import_task", lambda path: lambda: {"processed": 3, "failed": 1})
    err = StringIO()
    call_command("run_scheduled_tasks", stdout=StringIO(), stderr=err)
    assert "failed" in err.getvalue()
    assert PeriodicTaskRun.objects.get(name=command.SCHEDULED_TASKS[0][0]).last_error == "TaskReportedFailure"


def test_persisted_worker_continues_independent_domains_and_reports_failure(monkeypatch, settings):
    from apps.operations.cloud_jobs import work
    from apps.operations.cloud_jobs.contracts import JobsUnavailable
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    settings.TOMBSTONED_APPS = ()
    monkeypatch.setattr(work, "WORK", work.WORK[:2])
    calls = []

    def fail(**kwargs):
        calls.append("first")
        return {"failed": 1}

    def succeed(**kwargs):
        assert kwargs["limit"] == 25
        kwargs["fence"]()
        calls.append("second")

    monkeypatch.setattr(work, "_workers", {work.WORK[0].key: fail, work.WORK[1].key: succeed})
    with pytest.raises(JobsUnavailable, match="persisted_work_incomplete"):
        work.run_persisted_work(fence=lambda: None)
    assert calls == ["first", "second"]
