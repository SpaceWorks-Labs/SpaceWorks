"""Accept ciphertext quickly and stage it under a fenced per-job claim."""

from contextlib import contextmanager
from datetime import timedelta
import logging
import os
from pathlib import Path

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError as DrfValidationError

from apps.accounts.models import User
from apps.audit import services as audit
from apps.backup.digests import sha256_file
from apps.operations.models import PeriodicTaskRun

from .archive_retention import schedule_import_archive_unlink
from .archive_stream import PortableArchive
from .import_staging import decrypted_archive, seal_rows_sidecar
from .insertion_errors import TenantInsertionError
from .models_import_job import TenantImportJob
from .protocol_errors import ImportStateError, TenantMigrationProtocolError
from .services_import_job import _require_superadmin

logger = logging.getLogger(__name__)
STAGING_LEASE_DURATION = timedelta(hours=6)


class ImportStagingError(ImportStateError):
    code = "import_staging"


def staging_lease_name(job_id):
    return f"tenant-import-staging:{job_id}"


def rows_archive_path(job):
    if job.status == TenantImportJob.Status.UPLOADING:
        raise ImportStagingError("The encrypted archive is still being uploaded.")
    if job.status == TenantImportJob.Status.PENDING:
        raise ImportStagingError("The encrypted archive is still being staged.")
    sidecar = Path(f"{job.archive_path}.rows.age")
    return sidecar if sidecar.exists() else Path(job.archive_path)


@transaction.atomic
def accept_import_upload(*, actor, archive_path, size, source_archive_digest, expires_at):
    _require_superadmin(actor)
    job = TenantImportJob.objects.create(
        actor=actor, archive_path=str(archive_path),
        source_archive_digest=source_archive_digest, expires_at=expires_at,
        status=TenantImportJob.Status.PENDING,
    )
    audit.record(
        actor, "tenant_migration.import_upload_received", target=job,
        meta={
            "import_id": str(job.pk), "source_archive_digest": source_archive_digest,
            "archive_bytes": size, "format_version": 1,
        },
    )
    return job


@transaction.atomic
def _claim_staging_lease(job_id):
    now = timezone.now()
    lease, created = PeriodicTaskRun.objects.select_for_update().get_or_create(
        name=staging_lease_name(job_id), defaults={"last_run_at": now},
    )
    if not created and now - lease.last_run_at < STAGING_LEASE_DURATION:
        return None
    job = TenantImportJob.objects.select_for_update().filter(pk=job_id).first()
    if job is None or job.status != TenantImportJob.Status.PENDING or job.expires_at <= now:
        lease.delete()
        return None
    if not created:
        lease.last_run_at = now
        lease.save(update_fields=("last_run_at",))
    return lease.last_run_at, job


@contextmanager
def _staging_fence(job_id, token):
    """Use one lock order and ownership check for every staging path mutation."""
    with transaction.atomic():
        lease = PeriodicTaskRun.objects.select_for_update().filter(
            name=staging_lease_name(job_id), last_run_at=token,
        ).first()
        if lease is None:
            yield None
            return
        job = TenantImportJob.objects.select_for_update().filter(pk=job_id).first()
        now = timezone.now()
        if (
            job is None or job.status != TenantImportJob.Status.PENDING
            or job.expires_at <= now or now - lease.last_run_at >= STAGING_LEASE_DURATION
        ):
            yield None
            return
        yield lease, job


def _create_sidecar_part(job_id, token):
    output = None
    try:
        with _staging_fence(job_id, token) as owned:
            if owned is None:
                return None
            _lease, job = owned
            part = Path(f"{job.archive_path}.rows.age.part")
            # A superseded writer retains only the old, unlinked inode.
            part.unlink(missing_ok=True)
            output = part.open("xb")
            part.chmod(0o600)
        return output
    except Exception:
        if output is not None:
            output.close()
        raise


def _publish_staging(job_id, token, output, manifest, source, source_identity, users, actor):
    with _staging_fence(job_id, token) as owned:
        if owned is None:
            return
        lease, job = owned
        output.flush()
        os.fsync(output.fileno())
        output.close()
        os.replace(f"{job.archive_path}.rows.age.part", f"{job.archive_path}.rows.age")
        job.source_makerspace_id = str(source.get("id", ""))
        job.source_makerspace_slug = str(source.get("slug", ""))
        job.source_makerspace_name = str(source.get("name", ""))
        job.source_deployment_id = str(source_identity["deployment_id"])
        job.source_deployment_identity = source_identity
        job.storage_mode = ",".join(sorted(manifest.get("storage_mode", {}).values()))
        job.status = (
            TenantImportJob.Status.AWAITING_IDENTITY if users else TenantImportJob.Status.READY
        )
        job.save(update_fields=(
            "source_makerspace_id", "source_makerspace_slug", "source_makerspace_name",
            "source_deployment_id", "source_deployment_identity", "storage_mode",
            "status", "updated_at",
        ))
        audit.record(
            actor, "tenant_migration.import_created", target=job,
            meta={
                "import_id": str(job.pk), "identity_count": len(users),
                "format_version": manifest.get("format_version", 0),
                "source_archive_digest": job.source_archive_digest,
            },
        )
        lease.delete()


def _persist_staging_failure(job_id, token, actor, exc, failure_code):
    if failure_code is None:
        if isinstance(exc, (
            ValidationError, DrfValidationError, TenantInsertionError,
            TenantMigrationProtocolError, ValueError,
        )):
            failure_code = "invalid_archive"
        else:
            failure_code = "staging_failed"
            logger.exception("tenant_import_staging_failed", extra={"job_id": str(job_id)})
    detail = (
        "The encrypted archive could not be staged."
        if failure_code == "staging_failed" else str(exc).strip()[:500]
    )
    if isinstance(exc, ValidationError):
        detail = " ".join(exc.messages)[:500]
    elif isinstance(exc, DrfValidationError):
        detail = str(exc.detail)[:500]
    with _staging_fence(job_id, token) as owned:
        if owned is None:
            return
        lease, job = owned
        archive_path = job.archive_path
        updated = TenantImportJob.objects.filter(
            pk=job.pk, status=TenantImportJob.Status.PENDING,
        ).update(
            status=TenantImportJob.Status.FAILED, failure_code=failure_code,
            failure_detail=detail, terminal_at=timezone.now(), archive_path="",
            updated_at=timezone.now(),
        )
        if updated:
            audit.record(
                actor, "tenant_migration.import_staging_failed", target=job,
                meta={"import_id": str(job.pk), "failure_code": failure_code, "format_version": 1},
            )
            lease.delete()
            schedule_import_archive_unlink(archive_path, job.pk)


def stage_import_job(job_id, *, actor_id):
    claim = _claim_staging_lease(job_id)
    if claim is None:
        return TenantImportJob.objects.filter(pk=job_id).first()
    token, job = claim
    actor, output, failure_code = None, None, None
    try:
        actor = User.objects.filter(pk=actor_id).first()
        try:
            _require_superadmin(actor)
        except ValidationError as exc:
            failure_code = "forbidden"
            raise PermissionError("Superadmin access is required.") from exc
        if sha256_file(job.archive_path) != job.source_archive_digest:
            failure_code = "digest_mismatch"
            raise ValidationError({"detail": "The encrypted archive digest does not match."})
        with decrypted_archive(job.archive_path) as (root, _carried):
            portable = PortableArchive(root)
            manifest = portable.json("migration-manifest.json")
            from .archive_envelope import FORMAT, FORMAT_VERSION
            from .pairing import _validated_identity

            if (
                manifest.get("format") != FORMAT
                or manifest.get("format_version") != FORMAT_VERSION
            ):
                raise ValidationError({"detail": "The tenant migration format is unsupported."})
            source = manifest.get("source", {}).get("makerspace", {})
            source_identity = _validated_identity(
                manifest.get("source", {}).get("deployment"), "source"
            )
            users = list(portable.rows("accounts.User"))
            output = _create_sidecar_part(job_id, token)
            if output is None:
                return TenantImportJob.objects.filter(pk=job_id).first()
            seal_rows_sidecar(root, output)
        _publish_staging(job_id, token, output, manifest, source, source_identity, users, actor)
    except Exception as exc:
        if output is not None:
            output.close()
        _persist_staging_failure(job_id, token, actor, exc, failure_code)
    finally:
        if output is not None:
            output.close()
    return TenantImportJob.objects.filter(pk=job_id).first()
