"""Billing/account recovery runs on both supported schedulers."""
from io import StringIO

import pytest
from django.core.management import call_command

from apps.operations.management.commands import run_scheduled_tasks as runner


def test_all_beat_entries_including_account_reset_have_runner_counterparts(settings):
    assert {entry["task"] for entry in settings.CELERY_BEAT_SCHEDULE.values()} == {
        task for _, task, _ in runner.SCHEDULED_TASKS}
    assert ("missing-payment-bills", "apps.payments.tasks.issue_missing_bills_task", 5) in runner.SCHEDULED_TASKS
    assert ("drain-password-reset-envelopes", "apps.accounts.tasks.drain_password_reset_envelopes_task", 1) in runner.SCHEDULED_TASKS
    assert settings.CELERY_BEAT_SCHEDULE["missing-payment-bills"]["schedule"]._orig_minute == "*/5"


@pytest.mark.django_db
def test_beatless_bill_task_runs_once_per_five_minute_window(monkeypatch):
    from datetime import timedelta
    from django.utils import timezone
    from apps.operations.models_scheduling import PeriodicTaskRun
    calls = []
    monkeypatch.setattr(runner, "_import_task", lambda path: lambda: calls.append(path))
    options = {"task": "missing-payment-bills", "due_only": True, "stdout": StringIO()}
    call_command("run_scheduled_tasks", **options)
    # First discovery starts the interval; a new deployment does not run every task.
    assert calls == []
    PeriodicTaskRun.objects.filter(name="missing-payment-bills").update(last_run_at=timezone.now() - timedelta(minutes=6))
    call_command("run_scheduled_tasks", **options)
    call_command("run_scheduled_tasks", **options)
    assert calls == ["apps.payments.tasks.issue_missing_bills_task"]
    PeriodicTaskRun.objects.filter(name="missing-payment-bills").update(last_run_at=timezone.now() - timedelta(minutes=6))
    call_command("run_scheduled_tasks", **options)
    assert len(calls) == 2
