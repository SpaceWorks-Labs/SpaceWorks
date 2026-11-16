"""Daily scheduler parity and the explicit claim-token denial surface."""

from datetime import timedelta
from io import StringIO
from unittest.mock import Mock

import pytest
from django.conf import settings
from django.core.management import call_command
from django.urls import path, resolve, reverse
from django.utils import timezone

from apps.accounts import tasks
from apps.accounts.claim_pre_auth_guard import validate_pre_auth_route
from apps.accounts.claim_route_guard import validate_claim_route_matrix
from apps.accounts.claim_route_inspection import flatten_claim_routes
from apps.accounts.claim_route_types import AnonymousRead, Refused
from apps.accounts.claim_routes_auth import AUTH_CLAIM_ROUTES
from apps.accounts.models_mfa import MFAChallenge
from apps.accounts.models_reauthentication import ReauthenticationSession
from apps.operations.management.commands import run_scheduled_tasks as runner
from apps.operations.models import PeriodicTaskRun
from apps.tenant_migration.gate_policy_tasks import TASK_INTERNAL_PARTICIPANTS
from tests.accounts.claim_helpers_p7 import redeemed_claim
from tests.accounts.test_support_m1d import m1d_config

pytestmark = pytest.mark.django_db
TASK = "apps.accounts.tasks.purge_deleted_accounts_task"
ROUTES = {
    "auth-account-deletion": ("GET", "HEAD", "POST"),
    "auth-reauth-social-factor": ("POST",),
    "auth-reauth-phone-start": ("POST",),
    "auth-reauth-phone-confirm": ("POST",),
    "auth-account-restore-email": ("POST",),
    "auth-account-restore-phone": ("POST",),
    "auth-account-restore-social-start": ("POST",),
    "auth-account-restore-social-complete": ("POST",),
}


def test_daily_purge_has_same_cadence_and_callable_in_both_schedulers():
    entry = settings.CELERY_BEAT_SCHEDULE["purge-deleted-accounts"]
    assert entry["task"] == TASK
    assert len(entry["schedule"].hour) == 1 and len(entry["schedule"].minute) == 1
    assert entry["schedule"].day_of_week == set(range(7))
    assert ("purge-deleted-accounts", TASK, 1440) in runner.SCHEDULED_TASKS
    assert TASK in TASK_INTERNAL_PARTICIPANTS
    assert runner._import_task(TASK) is tasks.purge_deleted_accounts_task
    assert {row["task"] for row in settings.CELERY_BEAT_SCHEDULE.values()} == {
        task for _, task, _ in runner.SCHEDULED_TASKS}


def test_beatless_due_only_runs_purge_once_per_day(monkeypatch):
    invoke = Mock(return_value={"purged": 1, "skipped": 0, "failed": 0})
    monkeypatch.setattr(runner, "_import_task", lambda dotted: invoke)
    PeriodicTaskRun.objects.create(name="purge-deleted-accounts", last_run_at=timezone.now() - timedelta(days=2))
    out = StringIO()
    for _ in range(2):
        call_command("run_scheduled_tasks", "--task", "purge-deleted-accounts", "--due-only", stdout=out)
    invoke.assert_called_once_with()
    assert "ran purge-deleted-accounts" in out.getvalue()
    assert PeriodicTaskRun.objects.get(name="purge-deleted-accounts").last_error == ""


def test_celery_task_sweeps_apple_revocations_before_purging_accounts(monkeypatch):
    from apps.accounts import account_purge
    calls = []
    monkeypatch.setattr("apps.accounts.apple_revocation.sweep_revocations", lambda: calls.append("apple"))
    real_purge = account_purge.purge_account

    def purge(user_id, counts):
        calls.append("purge")
        return real_purge(user_id, counts)

    monkeypatch.setattr(account_purge, "purge_account", purge)
    from tests.accounts.test_support_m1d import account, due
    user = due(account())
    assert tasks.purge_deleted_accounts_task() == {"purged": 1, "skipped": 0, "failed": 0}
    assert calls == ["apple", "purge"]
    user.refresh_from_db()
    assert user.account_purged_at


def test_phase_1d_routes_pass_real_claim_inspection_and_explicit_matrix():
    patterns = [path("api/v1/auth/m1d/" + name, resolve(reverse(name)).func, name=name) for name in ROUTES]
    policies = {key: policy for key, policy in AUTH_CLAIM_ROUTES.items() if key[0] in ROUTES}
    inspected, errors = flatten_claim_routes(patterns)
    assert errors == []
    for route in inspected:
        assert validate_pre_auth_route(route) == []
    for name, methods in ROUTES.items():
        for method in methods:
            assert isinstance(policies[name, method], Refused)
        assert isinstance(policies[name, "OPTIONS"], AnonymousRead)
    assert len(validate_claim_route_matrix(patterns, policies=policies,
        require_all_active=False, check_middleware=True)) == len(ROUTES)
    # The all-active tree has its own guard in test_claim_routes. Keep this
    # integration contract scoped to every phase-1d route inspected above.


@pytest.mark.parametrize("name,method", [(name, method) for name, methods in ROUTES.items() for method in methods])
def test_real_claim_session_cannot_preview_delete_or_create_reauthentication_proof(name, method):
    harness = redeemed_claim("m1d-route")
    payload = {"confirm": "DELETE", "token": "fake", "code": "123456"}
    client = harness.claim_client
    response = getattr(client, method.lower())(reverse(name), data=payload, format="json")
    assert response.status_code == 403
    harness.member.refresh_from_db()
    assert harness.member.is_active and harness.member.deletion_requested_at is None
    assert not ReauthenticationSession.objects.filter(user=harness.member).exists()
    assert not MFAChallenge.objects.filter(user=harness.member).exists()
