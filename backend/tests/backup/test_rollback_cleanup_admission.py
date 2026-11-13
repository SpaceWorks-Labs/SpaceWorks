"""Age never authorizes deleting recovery material from an uncertain restore."""
from contextlib import nullcontext
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.backup import object_restore_cleanup as cleanup
from apps.backup.models import BackupArchive, DeploymentRecoveryState, RestoreOperation, RestoreRollbackObject

pytestmark = pytest.mark.django_db


def recovery_row(stage, *, terminal=True):
    archive = BackupArchive.objects.create(scope=BackupArchive.Scope.DEPLOYMENT,
        object_key="backup-archives/deployment/expiry.age", expires_at=timezone.now() + timedelta(days=1))
    restore = RestoreOperation.objects.create(archive=archive,
        kind=RestoreOperation.Kind.ROLLBACK_IN_PLACE, stage=stage,
        completed_at=timezone.now() if terminal else None)
    row = RestoreRollbackObject.objects.create(restore=restore, bucket_kind="private",
        source_key="evidence/restore.jpg", copy_key="rollback/retained/restore.jpg",
        expires_at=timezone.now() - timedelta(days=30))
    return restore, row


# Owner decision #42: full servers keep removing expired copies of failed/aborted
# restores (tests/backup/test_archive_retention_purge.py); only in-flight restores
# keep their aged recovery material.
@pytest.mark.parametrize("stage", [RestoreOperation.Stage.ROLLING_BACK, RestoreOperation.Stage.OBJECTS_RESTORING])
def test_aged_inflight_restore_is_preserved(monkeypatch, stage):
    _restore, row = recovery_row(stage)
    DeploymentRecoveryState.objects.update_or_create(pk=1, defaults={"mode": "normal", "active_restore": None})
    monkeypatch.setattr(cleanup, "deployment_operation_lock", lambda: nullcontext(object()))
    assert cleanup.cleanup_expired_rollback_objects() == 0
    assert RestoreRollbackObject.objects.filter(pk=row.pk).exists()


def test_terminal_cleanup_requires_no_active_recovery_and_deletes_once(monkeypatch):
    from apps.backup import storage
    restore, row = recovery_row(RestoreOperation.Stage.COMPLETED)
    DeploymentRecoveryState.objects.update_or_create(pk=1, defaults={"mode": "quiesced", "active_restore": restore})
    deleted = []
    monkeypatch.setattr(cleanup, "deployment_operation_lock", lambda: nullcontext(object()))
    monkeypatch.setattr(storage, "client", lambda: SimpleNamespace())
    monkeypatch.setattr("apps.backup.object_restore.delete_all_versions", lambda _client, **values: deleted.append(values))
    assert cleanup.cleanup_expired_rollback_objects() == 0
    assert not deleted
    DeploymentRecoveryState.objects.filter(pk=1).update(mode="normal", active_restore=None)
    assert cleanup.cleanup_expired_rollback_objects() == 1
    assert cleanup.cleanup_expired_rollback_objects() == 0
    assert len(deleted) == 1
    assert not RestoreRollbackObject.objects.filter(pk=row.pk).exists()
