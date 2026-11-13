from apps.operations.durable_dispatch import dispatch
"""Receive resumable ciphertext; decryption belongs to asynchronous staging."""

from datetime import timedelta
import logging
import os
from pathlib import Path
import re
from uuid import uuid4

from django.conf import settings
from django.db import transaction
from django.http import Http404
from django.utils import timezone

from apps.audit import services as audit

from .import_chunk_parser import CHUNK_MAX_BYTES
from .import_staging import MAX_ARCHIVE_BYTES
from .models_import_job import TenantImportJob
from .protocol_errors import (
    ImportStateError, UploadIncompleteError, UploadOffsetMismatchError,
)
from .services_import_job import _require_superadmin

logger = logging.getLogger(__name__)
UPLOAD_IDLE_TTL = timedelta(hours=24)


def start_import_upload(*, actor, source_archive_digest, archive_bytes):
    _require_superadmin(actor)
    if (
        type(archive_bytes) is not int or not 1 <= archive_bytes <= MAX_ARCHIVE_BYTES
        or not re.fullmatch(r"[0-9a-f]{64}", source_archive_digest)
    ):
        raise ValueError("A valid archive size and SHA-256 digest are required.")
    if settings.SPACEWORKS_DEPLOYMENT_MODE == "managed":
        from .cloud_import_upload import start
        return start(actor, source_archive_digest, archive_bytes)
    root = Path(settings.BACKUP_OPS_DIR, "tenant-imports")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = root / f"{uuid4()}.tar.age"
    created = False
    try:
        with path.open("xb"):
            created = True
            path.chmod(0o600)
        with transaction.atomic():
            job = TenantImportJob.objects.create(
                actor=actor, source_archive_digest=source_archive_digest,
                archive_path=str(path), status=TenantImportJob.Status.UPLOADING,
                upload_total_bytes=archive_bytes,
                expires_at=timezone.now() + UPLOAD_IDLE_TTL,
            )
            audit.record(
                actor, "tenant_migration.import_upload_started", target=job,
                meta={
                    "import_id": str(job.pk), "source_archive_digest": source_archive_digest,
                    "archive_bytes": archive_bytes, "format_version": 1,
                },
            )
        return job
    except Exception:
        if created:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                logger.exception(
                    "tenant_import_upload_unlink_failed", extra={"archive_path": str(path)},
                )
        raise


def _locked_job(job_id):
    # Uploads have no staging lease. Never acquire a lease after this job lock.
    job = TenantImportJob.objects.select_for_update().filter(pk=job_id).first()
    if job is None or job.expires_at <= timezone.now():
        raise Http404
    return job


def receive_import_chunk(*, actor, job_id, offset, chunk):
    _require_superadmin(actor)
    if type(offset) is not int or offset < 0 or not 1 <= len(chunk) <= CHUNK_MAX_BYTES:
        raise ValueError("A nonnegative offset and a nonempty chunk of at most 8 MiB are required.")
    if settings.SPACEWORKS_DEPLOYMENT_MODE == "managed":
        from .cloud_import_upload import receive
        return receive(actor, job_id, offset, chunk)
    with transaction.atomic():
        return _receive_local_chunk(actor, job_id, offset, chunk)


def _receive_local_chunk(actor, job_id, offset, chunk):
    job = _locked_job(job_id)
    if job.status != TenantImportJob.Status.UPLOADING:
        raise ImportStateError("This import is no longer accepting archive chunks.")
    if offset != job.upload_received_bytes:
        raise UploadOffsetMismatchError(job.upload_received_bytes)
    if job.upload_total_bytes is None or offset + len(chunk) > job.upload_total_bytes:
        raise ValueError("The chunk exceeds the declared archive size.")
    # Only local bounded disk I/O under the lock; the parser already read the network.
    with open(job.archive_path, "r+b") as output:
        output.seek(offset)
        if output.write(chunk) != len(chunk):
            raise OSError("The archive chunk could not be fully written.")
        output.flush()
        os.fsync(output.fileno())
    job.upload_received_bytes += len(chunk)
    job.expires_at = timezone.now() + UPLOAD_IDLE_TTL
    job.save(update_fields=("upload_received_bytes", "expires_at", "updated_at"))
    audit.record(
        actor, "tenant_migration.import_upload_chunk_received", target=job,
        meta={
            "import_id": str(job.pk), "offset": offset,
            "chunk_bytes": len(chunk), "format_version": 1,
        },
    )
    return job


def _dispatch_staging(job_id, actor_id):
    from .tasks import stage_import_job_task

    if not settings.CELERY_TASK_ALWAYS_EAGER:
        try:
            dispatch(stage_import_job_task, str(job_id), actor_id)
        except Exception:
            logger.exception(
                "tenant_import_staging_dispatch_failed", extra={"job_id": str(job_id)},
            )


def complete_import_upload(*, actor, job_id):
    _require_superadmin(actor)
    locator = None
    if settings.SPACEWORKS_DEPLOYMENT_MODE == "managed":
        from .cloud_import_upload import assemble
        candidate = TenantImportJob.objects.get(pk=job_id)
        if candidate.status == TenantImportJob.Status.UPLOADING:
            if candidate.upload_received_bytes != candidate.upload_total_bytes:
                raise UploadIncompleteError("The encrypted archive has not been fully uploaded.")
            locator = assemble(candidate)
    with transaction.atomic():
        return _complete_locked(actor, job_id, locator)


def _complete_locked(actor, job_id, locator):
    job = _locked_job(job_id)
    complete = (
        job.upload_total_bytes is not None
        and job.upload_received_bytes == job.upload_total_bytes
    )
    if job.status != TenantImportJob.Status.UPLOADING:
        if complete:
            return job  # A lost response must not duplicate audits or dispatch.
        raise ImportStateError("This import is not an archive upload session.")
    if not complete:
        raise UploadIncompleteError("The encrypted archive has not been fully uploaded.")
    job.status = TenantImportJob.Status.PENDING
    if locator:
        from apps.backup.managed.staging import select
        select(locator)
        job.archive_path = locator
    job.expires_at = timezone.now() + timedelta(seconds=settings.DATA_EXPORT_RETENTION_SECONDS)
    job.save(update_fields=("status", "archive_path", "expires_at", "updated_at"))
    audit.record(
        actor, "tenant_migration.import_upload_received", target=job,
        meta={
            "import_id": str(job.pk), "source_archive_digest": job.source_archive_digest,
            "archive_bytes": job.upload_total_bytes, "format_version": 1,
        },
    )
    transaction.on_commit(lambda: _dispatch_staging(job.pk, actor.pk))
    return job
