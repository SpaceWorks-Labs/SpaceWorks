"""integrations 0046: a fresh database starts sending; an upgraded one stays held."""

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

pytestmark = pytest.mark.django_db(transaction=True)

BEFORE = [("integrations", "0045_addressed_channels_survive_inbox_removal")]


def _rerun_0046(prepare=None):
    executor = MigrationExecutor(connection)
    leaves = executor.loader.graph.leaf_nodes()
    executor.migrate(BEFORE)
    from apps.integrations.models_cutover import NotificationCutover
    now = timezone.now()
    # The state 0041-0042 leave on any database before 0046 decides.
    NotificationCutover.objects.update_or_create(pk=1, defaults={
        "route": "receipt_only", "sending_enabled": False, "barrier_at": now, "copied_at": now,
        "reconciled_at": None, "activated_at": None, "snapshot": {}})
    if prepare:
        prepare()
    executor = MigrationExecutor(connection)
    executor.migrate(leaves)
    return NotificationCutover.objects.get(pk=1)


def test_empty_database_migrates_to_sending_allowed():
    from apps.integrations.notification_cutover import sending_allowed
    gate = _rerun_0046()
    assert gate.route == "canonical" and gate.sending_enabled
    assert gate.activated_at and gate.reconciled_at
    assert gate.snapshot["_install_branch"] == "fresh_install_active"
    assert sending_allowed() is True


def test_bootstrap_superuser_alone_still_counts_as_fresh():
    from apps.accounts.models import User
    from apps.integrations.notification_cutover import sending_allowed
    gate = _rerun_0046(lambda: User.objects.create_superuser(
        username="bootstrap", email="bootstrap@example.test", password="Bootstrap-pass-1!"))
    assert gate.snapshot["_install_branch"] == "fresh_install_active"
    assert sending_allowed() is True


def test_database_with_a_makerspace_stays_held():
    from apps.integrations.notification_cutover import sending_allowed
    from apps.makerspaces.models import Makerspace
    gate = _rerun_0046(lambda: Makerspace.objects.create(name="Existing", slug="existing-space"))
    assert gate.route == "receipt_only" and not gate.sending_enabled
    assert gate.activated_at is None and gate.reconciled_at is None
    assert gate.snapshot["_install_branch"] == "upgrade_held"
    assert sending_allowed() is False


def test_database_with_an_ordinary_account_stays_held():
    from apps.accounts.models import User
    from apps.integrations.notification_cutover import sending_allowed
    gate = _rerun_0046(lambda: User.objects.create_user(username="member", password="Member-pass-1!"))
    assert gate.snapshot["_install_branch"] == "upgrade_held"
    assert sending_allowed() is False


def test_an_already_activated_gate_is_left_alone():
    from apps.integrations.models_cutover import NotificationCutover
    executor = MigrationExecutor(connection)
    leaves = executor.loader.graph.leaf_nodes()
    executor.migrate(BEFORE)
    activated = timezone.now()
    NotificationCutover.objects.update_or_create(pk=1, defaults={
        "route": "canonical", "sending_enabled": True, "barrier_at": activated, "copied_at": activated,
        "reconciled_at": activated, "activated_at": activated, "snapshot": {"_verified": {}}})
    MigrationExecutor(connection).migrate(leaves)
    gate = NotificationCutover.objects.get(pk=1)
    assert gate.activated_at == activated and "_install_branch" not in gate.snapshot
