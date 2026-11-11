"""Portable identities never resurrect deleted accounts or a purged name."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.tenant_migration.identity_resolution import _create_walk_in

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("purged", [False, True])
def test_import_deleted_identity_is_inactive_with_timestamps(purged):
    now = timezone.now()
    source = {
        "username": "source-person", "first_name": "Private", "last_name": "Person", "display_name": "Private",
        "phone": "123456", "date_joined": (now - timedelta(days=200)).isoformat(),
        "deletion_requested_at": (now - timedelta(days=91)).isoformat(),
        "deletion_purge_after": (now - timedelta(days=1)).isoformat(),
        "account_purged_at": now.isoformat() if purged else "",
    }
    user = _create_walk_in(source, 987654)
    user.refresh_from_db()
    assert not user.is_active and not user.has_usable_password()
    assert user.deletion_requested_at == now - timedelta(days=91)
    assert user.deletion_purge_after == now - timedelta(days=1)
    assert user.account_purged_at == (now if purged else None)
    if purged:
        assert user.username.startswith("walkin_deleted_") and user.display_name == "Deleted member"
        assert "source" not in user.username and "person" not in user.username
        assert user.first_name == user.last_name == user.phone == ""


def test_daily_account_purge_has_scheduler_parity_and_gate_participation():
    from django.conf import settings
    from apps.operations.management.commands.run_scheduled_tasks import SCHEDULED_TASKS
    from apps.tenant_migration.gate_policy_tasks import TASK_INTERNAL_PARTICIPANTS
    task = "apps.accounts.tasks.purge_deleted_accounts_task"
    assert settings.CELERY_BEAT_SCHEDULE["purge-deleted-accounts"]["task"] == task
    assert ("purge-deleted-accounts", task, 24 * 60) in SCHEDULED_TASKS
    assert task in TASK_INTERNAL_PARTICIPANTS
