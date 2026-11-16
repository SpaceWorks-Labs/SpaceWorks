"""Resumable ciphertext uploads: bytes, offsets, audits, and staging handoff."""

from datetime import timedelta
import hashlib
import io
import os
from pathlib import Path
import stat
from unittest.mock import Mock

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.audit.models import AuditLog
from apps.tenant_migration import import_chunk_parser, services_import_upload
from apps.tenant_migration.import_job_cleanup import cleanup_expired_import_jobs
from apps.tenant_migration.models import TenantImportJob
from apps.tenant_migration.services_import_staging import stage_import_job
from apps.tenant_migration.views_import_upload import TenantImportArchiveChunkView
from tests.tenant_migration.test_import_async_staging import (
    actor, client_for, ops_dir, portable_tree, real_archive,
)

pytestmark = pytest.mark.django_db
MEDIA_TYPE = "application/offset+octet-stream"


def start(client, payload=b"encrypted archive"):
    return client.post(reverse("tenant-migration-import-upload-start"), {
        "source_archive_digest": hashlib.sha256(payload).hexdigest(),
        "archive_bytes": len(payload),
    }, format="json")


def chunk(client, job, payload, offset=0, **headers):
    return client.patch(
        reverse("tenant-migration-import-archive-chunk", args=(job.pk,)),
        payload, content_type=MEDIA_TYPE, HTTP_UPLOAD_OFFSET=str(offset), **headers,
    )


def complete(client, job):
    return client.post(reverse("tenant-migration-import-archive-complete", args=(job.pk,)))


@pytest.fixture
def uploading_job(actor, ops_dir):
    response = start(client_for(actor))
    assert response.status_code == 201
    return TenantImportJob.objects.get(pk=response.data["id"])


def test_start_creates_empty_private_file_and_audit(actor, ops_dir):
    payload = b"encrypted archive"
    response = start(client_for(actor), payload)
    assert response.status_code == 201
    assert response.data["status"] == "uploading"
    assert response.data["upload_received_bytes"] == 0
    assert response.data["upload_total_bytes"] == len(payload)
    job = TenantImportJob.objects.get(pk=response.data["id"])
    path = Path(job.archive_path)
    assert path.parent == ops_dir
    assert path.read_bytes() == b""
    if os.name == "posix":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    event = AuditLog.objects.get(action="tenant_migration.import_upload_started")
    assert event.actor_id == actor.pk
    assert event.meta == {
        "import_id": str(job.pk), "source_archive_digest": job.source_archive_digest,
        "archive_bytes": len(payload), "format_version": 1,
    }


def test_ordered_chunks_preserve_bytes_refresh_expiry_and_audit(actor, uploading_job):
    job, client = uploading_job, client_for(actor)
    old_expiry = timezone.now() + timedelta(minutes=1)
    TenantImportJob.objects.filter(pk=job.pk).update(expires_at=old_expiry)
    payload = b"encrypted archive"
    for offset, part in ((0, payload[:5]), (5, payload[5:])):
        response = chunk(client, job, part, offset)
        assert response.status_code == 200
        assert response.data["upload_received_bytes"] == offset + len(part)
        assert Path(job.archive_path).read_bytes() == payload[:offset + len(part)]
    job.refresh_from_db()
    assert job.expires_at > old_expiry
    events = AuditLog.objects.filter(
        action="tenant_migration.import_upload_chunk_received",
    ).order_by("created_at", "pk")
    assert [event.meta for event in events] == [
        {"import_id": str(job.pk), "offset": offset, "chunk_bytes": size, "format_version": 1}
        for offset, size in ((0, 5), (5, len(payload) - 5))
    ]
    assert all(event.actor_id == actor.pk for event in events)


@pytest.mark.parametrize("offset", [0, 1, 9])
def test_retry_or_wrong_offset_returns_authoritative_offset_without_writing(
    actor, uploading_job, offset,
):
    client, job = client_for(actor), uploading_job
    assert chunk(client, job, b"first").status_code == 200
    response = chunk(client, job, b"first", offset)
    assert response.status_code == 409
    assert response.data["code"] == "offset_mismatch"
    assert response.data["upload_received_bytes"] == 5
    job.refresh_from_db()
    assert job.upload_received_bytes == 5
    assert Path(job.archive_path).read_bytes() == b"first"
    assert AuditLog.objects.filter(action="tenant_migration.import_upload_chunk_received").count() == 1


@pytest.mark.parametrize("body,length,offset,media_type,status", [
    (b"", "0", "0", MEDIA_TYPE, 400),
    (b"12345", "5", "0", MEDIA_TYPE, 400),
    (b"x", None, "0", MEDIA_TYPE, 400),
    (b"x", "invalid", "0", MEDIA_TYPE, 400),
    (b"x", "-1", "0", MEDIA_TYPE, 400),
    (b"x", "1.0", "0", MEDIA_TYPE, 400),
    (b"x", "2", "0", MEDIA_TYPE, 400),
    (b"x", "1", None, MEDIA_TYPE, 400),
    (b"x", "1", "-1", MEDIA_TYPE, 400),
    (b"x", "1", "1.5", MEDIA_TYPE, 400),
    (b"x", "1", "garbage", MEDIA_TYPE, 400),
    (b"x", "1", "0", "application/octet-stream", 415),
])
def test_invalid_chunk_boundary_leaves_file_and_progress_unchanged(
    actor, uploading_job, monkeypatch, body, length, offset, media_type, status,
):
    monkeypatch.setattr(import_chunk_parser, "CHUNK_MAX_BYTES", 4)
    request = APIRequestFactory().generic("PATCH", "/chunk", body, content_type=media_type)
    # A BytesIO transport can represent a truncated network body without Django's
    # test FakePayload raising an assertion before the parser sees EOF.
    request._stream = io.BytesIO(body)
    if length is None:
        request.META.pop("CONTENT_LENGTH", None)
    else:
        request.META["CONTENT_LENGTH"] = length
    if offset is not None:
        request.META["HTTP_UPLOAD_OFFSET"] = offset
    force_authenticate(request, actor)
    response = TenantImportArchiveChunkView.as_view()(request, job_id=uploading_job.pk)
    assert response.status_code == status
    uploading_job.refresh_from_db()
    assert uploading_job.upload_received_bytes == 0
    assert Path(uploading_job.archive_path).read_bytes() == b""
    assert not AuditLog.objects.filter(action="tenant_migration.import_upload_chunk_received").exists()


def test_chunk_cannot_overflow_declared_total(actor, uploading_job):
    response = chunk(client_for(actor), uploading_job, b"x" * (uploading_job.upload_total_bytes + 1))
    assert response.status_code == 400
    uploading_job.refresh_from_db()
    assert uploading_job.upload_received_bytes == 0
    assert Path(uploading_job.archive_path).read_bytes() == b""


def test_complete_incomplete_upload_is_conflict(actor, uploading_job, monkeypatch):
    dispatch = Mock()
    monkeypatch.setattr("apps.tenant_migration.tasks.stage_import_job_task.delay", dispatch)
    response = complete(client_for(actor), uploading_job)
    assert response.status_code == 409
    assert response.data["code"] == "upload_incomplete"
    uploading_job.refresh_from_db()
    assert uploading_job.status == "uploading"
    assert not AuditLog.objects.filter(action="tenant_migration.import_upload_received").exists()
    dispatch.assert_not_called()


def test_complete_is_idempotent_and_dispatches_only_after_commit(
    actor, uploading_job, settings, monkeypatch, django_capture_on_commit_callbacks,
):
    settings.CELERY_TASK_ALWAYS_EAGER = False
    dispatch = Mock()
    monkeypatch.setattr("apps.tenant_migration.tasks.stage_import_job_task.delay", dispatch)
    client, job = client_for(actor), uploading_job
    assert chunk(client, job, b"encrypted archive").status_code == 200
    with django_capture_on_commit_callbacks(execute=True):
        first = complete(client, job)
        assert first.status_code == 202
        assert first.data["status"] == "pending"
        dispatch.assert_not_called()
    with django_capture_on_commit_callbacks(execute=True):
        second = complete(client, job)
    assert second.status_code == 202
    assert second.data["status"] == "pending"
    event = AuditLog.objects.get(action="tenant_migration.import_upload_received")
    assert event.meta == {
        "import_id": str(job.pk), "source_archive_digest": job.source_archive_digest,
        "archive_bytes": job.upload_total_bytes, "format_version": 1,
    }
    dispatch.assert_called_once_with(str(job.pk), actor.pk)


def test_real_age_archive_in_small_chunks_stages_to_identity(
    actor, ops_dir, real_archive, monkeypatch, settings,
):
    settings.CELERY_TASK_ALWAYS_EAGER = True
    monkeypatch.setattr(import_chunk_parser, "CHUNK_MAX_BYTES", 2048)
    monkeypatch.setattr(services_import_upload, "CHUNK_MAX_BYTES", 2048)
    client = client_for(actor)
    response = start(client, real_archive.payload)
    assert response.status_code == 201
    job = TenantImportJob.objects.get(pk=response.data["id"])
    for offset in range(0, len(real_archive.payload), 2048):
        assert chunk(client, job, real_archive.payload[offset:offset + 2048], offset).status_code == 200
    assert Path(job.archive_path).read_bytes() == real_archive.payload
    assert complete(client, job).status_code == 202
    assert stage_import_job(job.pk, actor_id=actor.pk).status == "awaiting_identity"
    job.refresh_from_db()
    assert job.source_makerspace_id == "41"
    assert Path(f"{job.archive_path}.rows.age").is_file()


@pytest.mark.parametrize("method", ["get", "post"])
def test_identity_refuses_uploading_before_archive_io(actor, uploading_job, monkeypatch, method):
    decrypt = Mock(side_effect=AssertionError("uploading archive must not be decrypted"))
    monkeypatch.setattr("apps.tenant_migration.import_staging.decrypted_archive", decrypt)
    url = reverse("tenant-migration-import-decisions", args=(uploading_job.pk,))
    client = client_for(actor)
    response = client.get(url) if method == "get" else client.post(url, {"decisions": []}, format="json")
    assert response.status_code == 409
    assert response.data["code"] == "import_staging"
    assert "still being uploaded" in response.data["detail"].lower()
    decrypt.assert_not_called()


def test_idle_upload_expiry_deletes_job_and_file(
    uploading_job, django_capture_on_commit_callbacks,
):
    now = timezone.now()
    TenantImportJob.objects.filter(pk=uploading_job.pk).update(expires_at=now - timedelta(seconds=1))
    with django_capture_on_commit_callbacks(execute=True):
        assert cleanup_expired_import_jobs(now=now) == 1
    assert not TenantImportJob.objects.filter(pk=uploading_job.pk).exists()
    assert not Path(uploading_job.archive_path).exists()


@pytest.mark.parametrize("operation", ["chunk", "complete"])
def test_expired_session_refuses_further_writes(actor, uploading_job, operation):
    TenantImportJob.objects.filter(pk=uploading_job.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
    client = client_for(actor)
    response = chunk(client, uploading_job, b"x") if operation == "chunk" else complete(client, uploading_job)
    assert response.status_code == 404
    assert Path(uploading_job.archive_path).read_bytes() == b""


def test_cleanup_rechecks_expiry_after_candidate_selection(
    uploading_job, monkeypatch, django_capture_on_commit_callbacks,
):
    from apps.tenant_migration import object_import

    now = timezone.now()
    job = uploading_job
    TenantImportJob.objects.filter(pk=job.pk).update(expires_at=now - timedelta(seconds=1))
    refreshed_expiry = now + timedelta(hours=24)

    def refresh_between_selection_and_lock(candidate):
        assert candidate.pk == job.pk
        # Candidate selection has finished, but the locked deletion recheck has
        # not started. Model the expiry/progress committed by an in-flight chunk.
        TenantImportJob.objects.filter(pk=job.pk).update(
            expires_at=refreshed_expiry, upload_received_bytes=1,
        )
        Path(job.archive_path).write_bytes(b"x")

    refresh = Mock(side_effect=refresh_between_selection_and_lock)
    monkeypatch.setattr(object_import, "rollback_import_objects", refresh)
    with django_capture_on_commit_callbacks(execute=True):
        assert cleanup_expired_import_jobs(now=now) == 0
    refresh.assert_called_once()
    job.refresh_from_db()
    assert job.status == "uploading"
    assert job.expires_at == refreshed_expiry
    assert job.upload_received_bytes == 1
    assert Path(job.archive_path).read_bytes() == b"x"
