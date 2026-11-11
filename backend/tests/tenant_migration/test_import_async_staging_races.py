"""Deterministic interleavings at staging's lease and filesystem boundaries."""

from contextlib import nullcontext
from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.operations.models import PeriodicTaskRun
from apps.tenant_migration import services_import_staging as staging, tasks
from apps.tenant_migration.import_job_cleanup import (
    cleanup_expired_import_jobs,
    resume_stale_pending_import_jobs,
)
from apps.tenant_migration.models import TenantImportJob
from tests.tenant_migration.test_import_async_staging import (
    actor, client_for, ops_dir, pending_job, portable_tree,
)

pytestmark = pytest.mark.django_db


class WorkerExit(BaseException):
    """A process death bypasses the service's ordinary exception handler."""


@pytest.fixture
def staging_io(monkeypatch, portable_tree):
    # Only the expensive crypto boundary is replaced for deterministic races.
    # Manifest/CSV readers, source identity validation, leases, DB writes, and
    # filesystem fencing remain real. The companion module tests real age I/O.
    monkeypatch.setattr(staging, "decrypted_archive", lambda _path: nullcontext(
        (portable_tree.root, ()),
    ))
    monkeypatch.setattr(staging, "seal_rows_sidecar", lambda _root, output: output.write(b"rows"))


def test_pending_identity_get_refuses_before_decryption(actor, pending_job, monkeypatch):
    job = pending_job()
    decrypt = Mock(side_effect=AssertionError("PENDING jobs must not be decrypted"))
    monkeypatch.setattr("apps.tenant_migration.import_staging.decrypted_archive", decrypt)
    response = client_for(actor).get(reverse("tenant-migration-import-decisions", args=(job.pk,)))
    assert response.status_code == 409
    assert response.data["code"] == "import_staging"
    decrypt.assert_not_called()
    job.refresh_from_db()
    assert job.status == "pending"


def test_pending_identity_post_refuses_before_decryption(actor, pending_job, monkeypatch):
    job = pending_job()
    decrypt = Mock(side_effect=AssertionError("PENDING jobs must not be decrypted"))
    monkeypatch.setattr("apps.tenant_migration.import_staging.decrypted_archive", decrypt)
    response = client_for(actor).post(
        reverse("tenant-migration-import-decisions", args=(job.pk,)),
        {"decisions": []}, format="json",
    )
    assert response.status_code == 409
    assert response.data["code"] == "import_staging"
    decrypt.assert_not_called()
    job.refresh_from_db()
    assert job.status == "pending"
    assert not job.identity_decisions.exists()


def test_redelivery_with_live_lease_does_not_touch_files(actor, pending_job, monkeypatch):
    job = pending_job()
    archive = Path(job.archive_path)
    part = Path(f"{archive}.rows.age.part")
    part.write_bytes(b"first attempt is still writing")
    token = timezone.now()
    PeriodicTaskRun.objects.create(name=staging.staging_lease_name(job.pk), last_run_at=token)
    digest = Mock(side_effect=AssertionError("redelivery must not read the archive"))
    unlink = Mock(side_effect=AssertionError("redelivery must not unlink"))
    rename = Mock(side_effect=AssertionError("redelivery must not publish"))
    monkeypatch.setattr(staging, "sha256_file", digest)
    monkeypatch.setattr(Path, "unlink", unlink)
    monkeypatch.setattr(staging.os, "replace", rename)

    result = staging.stage_import_job(job.pk, actor_id=actor.pk)

    assert result.status == "pending"
    assert archive.read_bytes() == b"encrypted archive"
    assert part.read_bytes() == b"first attempt is still writing"
    assert PeriodicTaskRun.objects.get(name=staging.staging_lease_name(job.pk)).last_run_at == token
    digest.assert_not_called()
    unlink.assert_not_called()
    rename.assert_not_called()
    assert not AuditLog.objects.filter(action="tenant_migration.import_created").exists()


def test_stale_attempt_after_takeover_cannot_publish_or_delete_b_part(
    actor, pending_job, staging_io, monkeypatch,
):
    job = pending_job()
    path = Path(job.archive_path)
    part = Path(f"{path}.rows.age.part")
    unlink = Mock(side_effect=AssertionError("stale A must not unlink B's paths"))
    rename = Mock(side_effect=AssertionError("stale A must not publish B's part"))
    replacement = timezone.now() + timedelta(seconds=1)

    def takeover(_root, output):
        output.write(b"attempt A")
        # Close A's descriptor as a suspended worker may have done; this also
        # permits the same deterministic interleaving on Windows filesystems.
        output.close()
        PeriodicTaskRun.objects.filter(name=staging.staging_lease_name(job.pk)).update(
            last_run_at=replacement,
        )
        part.unlink()
        part.write_bytes(b"attempt B must survive")
        monkeypatch.setattr(Path, "unlink", unlink)
        monkeypatch.setattr(staging.os, "replace", rename)

    monkeypatch.setattr(staging, "seal_rows_sidecar", takeover)
    staging.stage_import_job(job.pk, actor_id=actor.pk)

    job.refresh_from_db()
    assert job.status == "pending"
    assert job.source_makerspace_id == ""
    assert path.read_bytes() == b"encrypted archive"
    assert part.read_bytes() == b"attempt B must survive"
    assert not Path(f"{path}.rows.age").exists()
    assert PeriodicTaskRun.objects.get(name=staging.staging_lease_name(job.pk)).last_run_at == replacement
    unlink.assert_not_called()
    rename.assert_not_called()
    assert not AuditLog.objects.filter(
        action__in=("tenant_migration.import_created", "tenant_migration.import_staging_failed"),
    ).exists()


def test_expiry_cleanup_before_fenced_create_creates_no_part(
    actor, pending_job, staging_io, monkeypatch, django_capture_on_commit_callbacks,
):
    job = pending_job()
    path = Path(job.archive_path)
    create = staging._create_sidecar_part
    seal = Mock(side_effect=AssertionError("deleted job cannot create a sidecar"))
    opened = Mock(side_effect=AssertionError("no file may be opened after deletion"))
    monkeypatch.setattr(staging, "seal_rows_sidecar", seal)

    def expire_before_create(job_id, token):
        now = timezone.now()
        TenantImportJob.objects.filter(pk=job_id).update(expires_at=now - timedelta(seconds=1))
        with django_capture_on_commit_callbacks(execute=True):
            assert cleanup_expired_import_jobs(now=now) == 1
        # An implementation that creates then unlinks a part would leave no
        # orphan too, but still violates the fence. Observe the create itself.
        monkeypatch.setattr(Path, "open", opened)
        return create(job_id, token)

    monkeypatch.setattr(staging, "_create_sidecar_part", expire_before_create)
    assert staging.stage_import_job(job.pk, actor_id=actor.pk) is None
    opened.assert_not_called()
    seal.assert_not_called()
    assert not TenantImportJob.objects.filter(pk=job.pk).exists()
    assert all(not Path(f"{path}{suffix}").exists() for suffix in ("", ".rows.age", ".rows.age.part"))
    assert not PeriodicTaskRun.objects.filter(name=staging.staging_lease_name(job.pk)).exists()


def test_expiry_after_create_and_worker_death_unlinks_archive_sidecar_and_part(
    actor, pending_job, staging_io, monkeypatch, django_capture_on_commit_callbacks,
):
    job = pending_job()
    path = Path(job.archive_path)
    paths = [Path(f"{path}{suffix}") for suffix in ("", ".rows.age", ".rows.age.part")]

    def expire_after_create(_root, output):
        assert paths[2].is_file()
        output.write(b"interrupted seal")
        output.close()  # Process death closes its descriptor before cleanup runs.
        paths[1].write_bytes(b"old sidecar")
        now = timezone.now()
        TenantImportJob.objects.filter(pk=job.pk).update(expires_at=now - timedelta(seconds=1))
        with django_capture_on_commit_callbacks(execute=True):
            assert cleanup_expired_import_jobs(now=now) == 1
        raise WorkerExit("died after fenced create")

    monkeypatch.setattr(staging, "seal_rows_sidecar", expire_after_create)
    with pytest.raises(WorkerExit, match="after fenced create"):
        staging.stage_import_job(job.pk, actor_id=actor.pk)
    assert not TenantImportJob.objects.filter(pk=job.pk).exists()
    assert all(not candidate.exists() for candidate in paths)
    assert not PeriodicTaskRun.objects.filter(name=staging.staging_lease_name(job.pk)).exists()


def test_crash_mid_seal_is_recovered_by_next_attempt_then_expires_cleanly(
    actor, pending_job, staging_io, monkeypatch, django_capture_on_commit_callbacks,
):
    job = pending_job()
    path = Path(job.archive_path)
    part = Path(f"{path}.rows.age.part")

    def crash(_root, output):
        output.write(b"incomplete first seal")
        output.flush()
        raise WorkerExit("crash mid-seal")

    monkeypatch.setattr(staging, "seal_rows_sidecar", crash)
    with pytest.raises(WorkerExit, match="mid-seal"):
        staging.stage_import_job(job.pk, actor_id=actor.pk)
    assert part.read_bytes() == b"incomplete first seal"
    job.refresh_from_db()
    assert job.status == "pending"
    PeriodicTaskRun.objects.filter(name=staging.staging_lease_name(job.pk)).update(
        last_run_at=timezone.now() - timedelta(hours=7),
    )

    def complete(_root, output):
        assert part.read_bytes() == b""  # Fenced create replaced the crashed attempt.
        output.write(b"complete second seal")

    monkeypatch.setattr(staging, "seal_rows_sidecar", complete)
    assert staging.stage_import_job(job.pk, actor_id=actor.pk).status == "awaiting_identity"
    assert Path(f"{path}.rows.age").read_bytes() == b"complete second seal"
    assert not part.exists()
    now = timezone.now()
    TenantImportJob.objects.filter(pk=job.pk).update(expires_at=now - timedelta(seconds=1))
    with django_capture_on_commit_callbacks(execute=True):
        assert cleanup_expired_import_jobs(now=now) == 1
    assert not path.exists()
    assert not Path(f"{path}.rows.age").exists()


def test_pending_sweep_skips_live_lease_and_redispatches_lease_older_than_six_hours(
    pending_job, monkeypatch,
):
    now = timezone.now()
    live, stale = pending_job(), pending_job()
    TenantImportJob.objects.filter(pk__in=(live.pk, stale.pk)).update(
        created_at=now - timedelta(minutes=3),
    )
    PeriodicTaskRun.objects.create(name=staging.staging_lease_name(live.pk), last_run_at=now)
    PeriodicTaskRun.objects.create(
        name=staging.staging_lease_name(stale.pk), last_run_at=now - timedelta(hours=6, seconds=1),
    )
    dispatch = Mock()
    monkeypatch.setattr(tasks.stage_import_job_task, "delay", dispatch)
    assert resume_stale_pending_import_jobs(now=now) == 1
    dispatch.assert_called_once_with(str(stale.pk), stale.actor_id)
    assert resume_stale_pending_import_jobs(now=now) == 0  # Sweep lease prevents duplicates.
    dispatch.assert_called_once()


def test_expiry_cleanup_deletes_only_deleted_jobs_staging_leases(
    pending_job, django_capture_on_commit_callbacks,
):
    now = timezone.now()
    expired = pending_job(expires_at=now - timedelta(seconds=1))
    live = pending_job()
    for job in (expired, live):
        PeriodicTaskRun.objects.create(name=staging.staging_lease_name(job.pk), last_run_at=now)
    with django_capture_on_commit_callbacks(execute=True):
        assert cleanup_expired_import_jobs(now=now) == 1
    assert not TenantImportJob.objects.filter(pk=expired.pk).exists()
    assert not PeriodicTaskRun.objects.filter(name=staging.staging_lease_name(expired.pk)).exists()
    assert TenantImportJob.objects.filter(pk=live.pk).exists()
    assert PeriodicTaskRun.objects.filter(name=staging.staging_lease_name(live.pk)).exists()
    assert not Path(expired.archive_path).exists()
    assert Path(live.archive_path).exists()


def test_recovery_task_returns_sum_including_staging_sweep(monkeypatch):
    finalizing, pending, materializing = Mock(return_value=2), Mock(return_value=3), Mock(return_value=0)
    monkeypatch.setattr(tasks, "resume_expired_finalizing_import_jobs", finalizing)
    monkeypatch.setattr(tasks, "resume_stale_pending_import_jobs", pending)
    monkeypatch.setattr(tasks, "resume_stalled_materializations", materializing)
    assert tasks.resume_expired_finalizing_import_jobs_task.run() == 5
    finalizing.assert_called_once_with()
    pending.assert_called_once_with()
    materializing.assert_called_once_with()
