"""Local-only integration regressions; execute with isolated PostgreSQL migrations."""
from datetime import timedelta
from pathlib import Path
import uuid

import pytest
from django.db import DatabaseError, connection, transaction
from django.utils import timezone

from apps.backup.managed.models_staging import ManagedStagedObject
from apps.backup.managed import staging

pytestmark = pytest.mark.django_db(transaction=True)


def object_row(**extra):
    row_id = uuid.uuid4()
    return ManagedStagedObject.objects.create(owner=uuid.uuid4(), label="archive",
        identity={"endpoint": "https://storage.invalid", "region": "auto", "bucket": "private"},
        object_key=f"managed-staging/{row_id}.age", sha256="a" * 64, size=6,
        expires_at=timezone.now() + timedelta(hours=1), **extra)


def test_lineage_cannot_be_retargeted_or_deleted_by_raw_sql():
    row = object_row()
    for change, values in (("object_key=%s", ["other"]), ("sha256=%s", ["b" * 64]),
                           ("owner=%s", [str(uuid.uuid4())]), ("size=%s", [100])):
        with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(f"UPDATE backup_managedstagedobject SET {change} WHERE id=%s", [*values, str(row.pk)])
    with pytest.raises(DatabaseError), transaction.atomic():
        row.delete()


def test_losing_upload_attempt_cannot_replace_selected_slot():
    first = object_row(available=True)
    second = ManagedStagedObject.objects.create(owner=first.owner, label=first.label,
        identity=first.identity, object_key=f"managed-staging/{uuid.uuid4()}.age", sha256="b" * 64,
        size=9, expires_at=first.expires_at, available=True)
    staging.select(staging.PREFIX + str(first.pk))
    with pytest.raises(DatabaseError), transaction.atomic():
        staging.select(staging.PREFIX + str(second.pk))
    assert staging.latest(first.owner, "archive") == staging.PREFIX + str(first.pk)


def test_expired_object_cannot_be_published():
    row = object_row(available=True)
    # Use creation of an expired receipt: expiry itself is immutable too.
    expired = ManagedStagedObject.objects.create(owner=uuid.uuid4(), label="archive",
        identity=row.identity, object_key=f"managed-staging/{uuid.uuid4()}.age", size=1,
        expires_at=timezone.now() - timedelta(seconds=1), available=True)
    with pytest.raises(ValueError):
        staging.select(staging.PREFIX + str(expired.pk))


def test_cross_process_materialization_checks_full_digest_and_closes_body(monkeypatch, tmp_path):
    import hashlib
    from io import BytesIO
    row_id = uuid.uuid4()
    row = ManagedStagedObject.objects.create(owner=row_id, label="archive", identity={},
        object_key=f"managed-staging/{row_id}.age", size=6, sha256=hashlib.sha256(b"cipher").hexdigest(),
        available=True, expires_at=timezone.now() + timedelta(hours=1))
    body = BytesIO(b"cipher")
    class Client:
        def get_object(self, **kwargs):
            return {"Body": body}
        def close(self):
            pass
    monkeypatch.setattr(staging, "_client", lambda row=None: (Client(), {}))
    monkeypatch.setattr("apps.operations.cloud_runtime.check", lambda: None)
    with staging.materialize(staging.PREFIX + str(row.pk)) as path:
        assert path.read_bytes() == b"cipher"
        local = path
    assert body.closed and not local.exists()


def test_physical_pin_loss_refuses_before_any_writer_state_query():
    from apps.backup.managed.writers import WriterBoundary
    class Pin:
        def assert_valid(self):
            raise RuntimeError("lost physical session")
    with pytest.raises(RuntimeError, match="lost physical session"):
        WriterBoundary(None, Pin()).assert_valid()


def test_pause_drains_actual_presign_expiry_and_refuses_active_writer(settings):
    from apps.backup.managed.models import ManagedCaptureState, ManagedWriterBoundary
    from apps.backup.managed.models_staging import ManagedPresignLease
    from apps.backup.managed.writers import pause_capture, assert_capture_drained, WriterFenceError
    state, _ = ManagedCaptureState.objects.get_or_create(pk=1)
    class Guard:
        def assert_valid(self):
            pass
    owner, guard = uuid.uuid4(), Guard()
    expiry = timezone.now() + timedelta(hours=2)
    ManagedPresignLease.objects.create(generation=state.generation, expires_at=expiry)
    paused = pause_capture(owner, guard, max_presign_ttl=1, transfer_bound=1)
    assert paused.drain_until >= expiry
    ManagedCaptureState.objects.filter(pk=1).update(drain_until=timezone.now() - timedelta(seconds=1))
    ManagedWriterBoundary.objects.create(generation=state.generation, category="web")
    with pytest.raises(WriterFenceError, match="writers"):
        assert_capture_drained(owner, guard)


def test_lost_capture_guard_never_clears_durable_pause(settings):
    from apps.backup.managed.models import ManagedCaptureState
    from apps.backup.managed.writers import pause_capture
    from apps.backup.managed.capture import capture_pause
    from apps.backup.cloud_continuity import operation_guard
    state, _ = ManagedCaptureState.objects.get_or_create(pk=1)
    settings.MANAGED_UPLOAD_TRANSFER_BOUND_SECONDS = 1
    class Guard:
        lost = False
        def assert_valid(self):
            if self.lost:
                raise RuntimeError("capture guard lost")
    owner, guard = uuid.uuid4(), Guard()
    with operation_guard(guard):
        pause_capture(owner, guard, max_presign_ttl=1, transfer_bound=1)
        guard.lost = True
        with pytest.raises(RuntimeError, match="guard lost"):
            with capture_pause(owner):
                pytest.fail("A lost owner must not start capture")
        guard.lost = False
    assert ManagedCaptureState.objects.get(pk=1).paused_by == owner
