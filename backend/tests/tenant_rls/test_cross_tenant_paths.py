"""Each cross-tenant capability path is listed, audited and pinned; anything else sees no other rows."""

import pytest
from django.db import DatabaseError, transaction
from django.urls import get_resolver

from apps.audit.models import AuditLog
from apps.tenant_rls.capabilities import CAPABILITIES, PATH_CAPABILITIES, ROUTE_CAPABILITIES, TASK_CAPABILITIES
from apps.tenant_rls.context import capability_context, tenant_context

from .conftest import labels

pytestmark = pytest.mark.django_db

PINNED = {
    "public_directory", "platform_console", "platform_reports", "backup", "per_space_restore",
    "notification_fanout", "tenant_migration", "collaboration",
}


def test_the_capability_registry_is_pinned():
    assert set(CAPABILITIES) == PINNED
    assert set(ROUTE_CAPABILITIES.values()) | {name for _, name in PATH_CAPABILITIES} | set(
        TASK_CAPABILITIES.values()) <= PINNED
    assert PATH_CAPABILITIES == (("/control/", "platform_console"),)


def test_every_registered_route_and_task_exists():
    names = {name for name in get_resolver().reverse_dict if isinstance(name, str)}
    assert set(ROUTE_CAPABILITIES) <= names, set(ROUTE_CAPABILITIES) - names
    from config.celery import app
    app.loader.import_default_modules()
    assert set(TASK_CAPABILITIES) <= set(app.tasks), set(TASK_CAPABILITIES) - set(app.tasks)


def test_lane_d_and_b2_paths_hold_their_capability():
    assert ROUTE_CAPABILITIES["admin-platform-dashboard"] == "platform_reports"
    assert ROUTE_CAPABILITIES["admin-makerspace-restores"] == "per_space_restore"
    assert TASK_CAPABILITIES["apps.backup.tasks_space_restore.run_space_restore_apply_task"] == "per_space_restore"
    assert TASK_CAPABILITIES["apps.integrations.notification_tasks.sweep_notification_outbox"] == "notification_fanout"


@pytest.mark.parametrize("name", sorted(PINNED))
def test_each_capability_reads_across_tenants_and_is_audited(probe, boxes, name):
    a = boxes[0].makerspace
    with tenant_context(a.pk):
        assert labels() == ["A box"]
        with capability_context(name, label=f"test:{name}", actor_kind="task"):
            assert labels() == ["A box", "B box"]
    row = AuditLog.objects.filter(action="rls.capability_used").latest("id")
    assert row.meta == {"capability": name, "path": f"test:{name}", "actor_kind": "task"}


def test_an_unregistered_capability_is_refused():
    with pytest.raises(ValueError):
        with capability_context("everything"):
            pass


def test_without_a_capability_other_tenants_rows_cannot_be_written(probe, boxes):
    from apps.boxes.models import Box
    a, b = (box.makerspace for box in boxes)
    with tenant_context(a.pk):
        with pytest.raises(DatabaseError), transaction.atomic():
            Box.objects.create(makerspace=b, label="planted")
        assert Box.objects.filter(pk=boxes[1].pk).update(label="hijacked") == 0
        assert Box.objects.filter(pk=boxes[1].pk).delete()[0] == 0
    assert Box.objects.get(pk=boxes[1].pk).label == "B box"
