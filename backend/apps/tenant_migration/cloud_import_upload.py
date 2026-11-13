"""Cross-process chunks: remote bytes first, then a short offset CAS transaction."""
from datetime import timedelta
from pathlib import Path
import tempfile
import uuid

from django.db import transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.backup.managed import staging
from .models_import_job import TenantImportJob
from .protocol_errors import ImportStateError, UploadOffsetMismatchError


def start(actor, digest, size):
    from django.conf import settings
    if settings.SPACEWORKS_DEPLOYMENT_PROFILE == "free" and size > settings.FREE_MAX_PROMOTION_BYTES:
        raise ValueError("This archive requires an external import job.")
    with transaction.atomic():
        job = TenantImportJob.objects.create(actor=actor, source_archive_digest=digest,
            status=TenantImportJob.Status.UPLOADING, upload_total_bytes=size,
            expires_at=timezone.now() + timedelta(hours=24))
        job.archive_path = "cloud-upload:" + str(job.pk)
        job.save(update_fields=["archive_path"])
        audit.record(actor, "tenant_migration.import_upload_started", target=job,
            meta={"import_id": str(job.pk), "source_archive_digest": digest,
                  "archive_bytes": size, "format_version": 1})
    return job


def receive(actor, job_id, offset, chunk):
    job = TenantImportJob.objects.get(pk=job_id)
    if job.status != TenantImportJob.Status.UPLOADING or job.expires_at <= timezone.now():
        raise ImportStateError("This import is no longer accepting chunks.")
    if offset != job.upload_received_bytes:
        raise UploadOffsetMismatchError(job.upload_received_bytes)
    if offset + len(chunk) > job.upload_total_bytes:
        raise ValueError("The chunk exceeds the declared archive size.")
    with tempfile.TemporaryDirectory(prefix="spaceworks-chunk-") as directory:
        path = Path(directory, "chunk.age")
        path.write_bytes(chunk)
        path.chmod(0o600)
        locator = staging.store(path, owner=job.pk, label=f"chunk:{offset}", expires_at=job.expires_at)
    with transaction.atomic():
        locked = TenantImportJob.objects.select_for_update().get(pk=job.pk)
        if locked.status != job.status or locked.expires_at <= timezone.now() or locked.upload_received_bytes != offset:
            # This upload intent remains discoverable for conservative retained cleanup.
            staging.retire(locator)
            raise UploadOffsetMismatchError(locked.upload_received_bytes)
        staging.select(locator)
        locked.upload_received_bytes += len(chunk)
        locked.save(update_fields=["upload_received_bytes", "updated_at"])
        audit.record(actor, "tenant_migration.import_upload_chunk_received", target=locked,
            meta={"import_id": str(job.pk), "offset": offset, "chunk_bytes": len(chunk), "format_version": 1})
    return locked


def assemble(job):
    """Stream verified chunks into disposable local scratch, never process memory."""
    from apps.backup.digests import sha256_file
    from .import_chunk_parser import CHUNK_MAX_BYTES
    from django.conf import settings
    with tempfile.TemporaryDirectory(prefix="spaceworks-import-") as directory:
        path, offset = Path(directory, "archive.age"), 0
        with path.open("xb") as output:
            while offset < job.upload_total_bytes:
                locator = staging.latest(job.pk, f"chunk:{offset}")
                if locator is None:
                    raise ImportStateError("An uploaded archive chunk is unavailable.")
                with staging.materialize(locator) as part, part.open("rb") as source:
                    size = part.stat().st_size
                    if size < 1 or size > CHUNK_MAX_BYTES or offset + size > job.upload_total_bytes:
                        raise ImportStateError("Archive chunk boundaries are invalid.")
                    while data := source.read(1024 * 1024):
                        output.write(data)
                offset += size
        if sha256_file(path) != job.source_archive_digest:
            raise ImportStateError("The encrypted archive digest does not match.")
        return staging.store(path, owner=job.pk, label="archive", expires_at=max(
            job.expires_at, timezone.now() + timedelta(seconds=settings.DATA_EXPORT_RETENTION_SECONDS)))


def accept_file(actor, path, size, digest, expires_at):
    from .services_import_job import _require_superadmin
    _require_superadmin(actor)
    owner = uuid.uuid4()
    locator = staging.store(path, owner=owner, label="archive", expires_at=expires_at)
    with transaction.atomic():
        job = TenantImportJob.objects.create(id=owner, actor=actor, archive_path=locator,
            source_archive_digest=digest, expires_at=expires_at, status=TenantImportJob.Status.PENDING)
        audit.record(actor, "tenant_migration.import_upload_received", target=job,
            meta={"import_id": str(job.pk), "source_archive_digest": digest,
                  "archive_bytes": size, "format_version": 1})
    Path(path).unlink(missing_ok=True)
    return job
