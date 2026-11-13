"""The audit verification Celery task maps each outcome to a closed result and never stores exception text."""

from types import SimpleNamespace
from unittest.mock import patch

from celery.exceptions import SoftTimeLimitExceeded

from apps.audit import tasks_verification as tasks
from apps.audit.verification_execution import RetryAttempt


def run(side_effect=None, result=None):
    with patch.object(tasks, "execute_attempt", side_effect=side_effect, return_value=result) as execute,             patch.object(tasks, "fail_attempt") as fail, patch("apps.audit.verification_runs._enqueue") as enqueue:
        outcome = tasks.run_audit_verification.run(7)
    return outcome, execute, fail, enqueue


def test_a_finished_attempt_returns_the_event_state():
    outcome, execute, fail, enqueue = run(result=SimpleNamespace(state="succeeded"))
    assert outcome == "succeeded"
    execute.assert_called_once_with(7)
    fail.assert_not_called()
    enqueue.assert_not_called()


def test_an_attempt_that_did_nothing_is_reported_as_skipped():
    assert run(result=None)[0] == "skipped"


def test_a_retry_request_schedules_the_next_delivery_after_thirty_seconds():
    outcome, _execute, fail, enqueue = run(side_effect=RetryAttempt())
    assert outcome == "retrying"
    enqueue.assert_called_once_with(7, countdown=30)
    fail.assert_not_called()


def test_a_soft_time_limit_fails_the_attempt_with_a_closed_code():
    outcome, _execute, fail, enqueue = run(side_effect=SoftTimeLimitExceeded())
    assert outcome == "timed_out"
    fail.assert_called_once_with(7, "soft_time_limit")
    enqueue.assert_not_called()


def test_any_other_exception_fails_the_attempt_and_logs_but_does_not_store_the_text(caplog):
    with caplog.at_level("ERROR"):
        outcome, _execute, fail, enqueue = run(side_effect=RuntimeError("secret detail"))
    assert outcome == "failed"
    fail.assert_called_once_with(7, "task_error")
    assert "audit_verification_task_error" in caplog.text
    assert all("secret detail" not in str(call) for call in fail.call_args_list)
    enqueue.assert_not_called()


def test_the_task_has_a_stable_name_and_never_auto_retries():
    assert tasks.run_audit_verification.name == "apps.audit.tasks.run_audit_verification"
    assert tasks.run_audit_verification.max_retries == 0
