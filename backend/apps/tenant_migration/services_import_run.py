"""Execute claimed imports with lock retention and attempt-token fencing."""

import logging
import uuid

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.audit import services as audit

from .import_run_lock import import_run_lock
from .insertion_errors import (
    ImportCompletionAuditError,
    ImportPromotionClaimLost,
    ImportPromotionInProgress,
    MaterializationAlreadyCommitted,
    MaterializationSuperseded,
)
from .models_import_job import TenantImportJob


logger = logging.getLogger(__name__)


def run_import_job(job_id, *, actor_id, target_identity=None):
    from .services_import_job import _require_superadmin

    job = TenantImportJob.objects.get(pk=job_id)
    if job.status == TenantImportJob.Status.COMPLETED:
        return job
    if job.status == TenantImportJob.Status.FINALIZING:
        actor = User.objects.get(pk=actor_id)
        _require_superadmin(actor)
        return _execute(job, actor=actor)
    if job.status != TenantImportJob.Status.MATERIALIZING:
        raise ValidationError({"detail": "The import has not been claimed for execution."})

    with import_run_lock(job.pk) as lock:
        if not lock.acquired:
            return TenantImportJob.objects.get(pk=job.pk)
        # No exception before a successful claim may transition status or clean objects.
        attempt = _claim_attempt(job.pk, lock)
        if attempt is None:
            return TenantImportJob.objects.get(pk=job.pk)
        actor = User.objects.filter(pk=actor_id).first()
        try:
            _require_superadmin(actor)
        except ValidationError:
            return _refuse_requester(job.pk, actor, attempt)
        return _execute(
            job, actor=actor, target_identity=target_identity,
            attempt=attempt, lock=lock,
        )


@transaction.atomic
def _claim_attempt(job_id, lock):
    job = TenantImportJob.objects.select_for_update().get(pk=job_id)
    if (
        job.status != TenantImportJob.Status.MATERIALIZING
        or job.target_makerspace_id is not None
        or not lock.retained()
    ):
        return None
    # Retention MUST be checked under this row lock, before writing the token.
    job.run_attempt = uuid.uuid4()
    job.save(update_fields=("run_attempt", "updated_at"))
    return job.run_attempt


@transaction.atomic
def _refuse_requester(job_id, actor, attempt):
    updated = TenantImportJob.objects.filter(
        pk=job_id, status=TenantImportJob.Status.MATERIALIZING,
        target_makerspace__isnull=True, run_attempt=attempt,
    ).update(
        status=TenantImportJob.Status.FAILED, failure_code="forbidden",
        failure_detail="Superadmin access is required.",
        terminal_at=timezone.now(), updated_at=timezone.now(),
    )
    job = TenantImportJob.objects.get(pk=job_id)
    if updated:
        audit.record(
            actor, "tenant_migration.import_run_refused", target=job,
            meta={"import_id": str(job.pk), "failure_code": "forbidden", "format_version": 1},
        )
    return job


def _execute(job, *, actor, target_identity=None, attempt=None, lock=None):
    from .import_finalization import finalize_import_job
    from .materialization import materialize_tenant

    try:
        if attempt is not None:
            from .import_staging import decrypted_archive

            try:
                with decrypted_archive(job.archive_path) as (root, carried):
                    materialize_tenant(
                        root, job, carried, target_identity=target_identity,
                        run_attempt=attempt, run_lock=lock,
                    )
            except MaterializationAlreadyCommitted:
                pass
        job.refresh_from_db()
        return finalize_import_job(job, actor=actor)
    except (MaterializationSuperseded, ImportPromotionClaimLost, ImportPromotionInProgress):
        # The replacement's status and objects are authoritative.
        return TenantImportJob.objects.get(pk=job.pk)
    except ImportCompletionAuditError:
        # Preserve FINALIZING so the scheduled sweep can retry atomic completion.
        raise
    except Exception as exc:
        logger.exception(
            "tenant_import_execution_failed",
            extra={"job_id": str(job.pk), "run_attempt": str(attempt) if attempt else None},
        )
        _record_failure(job, exc, attempt=attempt)
        raise


def _record_failure(job, error, *, attempt):
    failure_detail = str(error).strip()[:500] or type(error).__name__
    owned = TenantImportJob.objects.filter(pk=job.pk)
    if attempt is not None:
        owned = owned.filter(run_attempt=attempt)
    failed_active = owned.filter(
        status__in=(TenantImportJob.Status.MATERIALIZING, TenantImportJob.Status.FINALIZING),
    ).update(
        status=TenantImportJob.Status.FAILED,
        failure_code="materialization_failed", failure_detail=failure_detail,
        terminal_at=timezone.now(),
    )
    if failed_active:
        from .object_import import rollback_import_objects

        rollback_job = TenantImportJob.objects.select_related(
            "target_makerspace", "actor"
        ).get(pk=job.pk)
        rollback_import_objects(rollback_job)
    else:
        # Only annotate the matching attempt's unexplained failure. A superseded
        # MATERIALIZING attempt neither changes status nor rolls back shared objects.
        owned.filter(
            status=TenantImportJob.Status.FAILED, failure_code="", failure_detail="",
        ).update(failure_code="materialization_failed", failure_detail=failure_detail)
