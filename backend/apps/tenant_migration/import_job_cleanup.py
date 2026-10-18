from apps.operations.cloud_jobs import bounded
from apps.operations.durable_dispatch import dispatch
"""Bounded retention jobs for tenant-import rows, archives, and object journals."""

import logging
from datetime import timedelta

from django.db import transaction
from django.db.models import CharField, Exists, OuterRef, Q, Value
from django.db.models.functions import Cast, Concat
from django.utils import timezone

from apps.operations.models import PeriodicTaskRun

from .archive_retention import schedule_import_archive_unlink
from .models_import_job import TenantImportJob
from .models_import_objects import TenantImportObject
from .object_promotion import PROMOTION_LEASE_DURATION


CLEANUP_LEASE_NAME = "tenant-import-expiry-cleanup-work"
CLEANUP_OBJECTS_LEASE_NAME = "tenant-import-object-cleanup-work"
FINALIZATION_SWEEP_LEASE_NAME = "tenant-import-finalization-sweep-work"
STAGING_SWEEP_LEASE_NAME = "tenant-import-staging-sweep-work"
MATERIALIZATION_SWEEP_LEASE_NAME = "tenant-import-materialization-sweep-work"
CLEANUP_LEASE_DURATION = timedelta(minutes=15)
FINALIZATION_SWEEP_LEASE_DURATION = timedelta(minutes=5)
MATERIALIZATION_RESUME_GRACE = timedelta(minutes=2)
DEFAULT_CLEANUP_BATCH_SIZE = 100


logger = logging.getLogger(__name__)


def cleanup_expired_import_jobs(*, now=None, batch_size=DEFAULT_CLEANUP_BATCH_SIZE):
    """Delete pre-tenant jobs and expire archives retained by terminal target jobs."""
    batch_size = bounded.limit(batch_size)
    cleanup_at = now or timezone.now()
    if not _claim_named_cleanup_lease(CLEANUP_LEASE_NAME, cleanup_at):
        return 0

    candidates = list(
        TenantImportJob.objects.filter(expires_at__lte=cleanup_at)
        .filter(
            Q(target_makerspace__isnull=True)
            | (
                Q(status__in=TenantImportJob.TERMINAL_STATUSES)
                & ~Q(archive_path="")
            )
        )
        .order_by("expires_at", "pk")
        .values("pk", "target_makerspace_id", "archive_path")[:batch_size]
    )
    delete_ids = [row["pk"] for row in candidates if row["target_makerspace_id"] is None]

    # Object-storage cleanup is external I/O and stays outside the deletion transaction.
    if delete_ids:
        from .object_import import rollback_import_objects

        for job in bounded.page(TenantImportJob.objects.filter(pk__in=delete_ids), "import-delete-jobs"):
            rollback_import_objects(job)

    with transaction.atomic():
        from .services_import_staging import staging_lease_name

        leases = PeriodicTaskRun.objects.select_for_update().filter(
            name__in=[staging_lease_name(job_id) for job_id in delete_ids],
        ).order_by("name")
        lease_ids = {lease.name: lease.pk for lease in leases}
        # A chunk may have refreshed expiry while cleanup waited. Recheck the
        # locked rows, rather than deleting the earlier candidate IDs blindly.
        locked = list(TenantImportJob.objects.select_for_update().filter(
            pk__in=[row["pk"] for row in candidates],
        ).order_by("pk"))
        delete_ids, cleared = [], 0
        for job in bounded.items(locked):
            if job.expires_at > cleanup_at:
                continue
            if job.target_makerspace_id is None:
                delete_ids.append(job.pk)
            elif job.status in TenantImportJob.TERMINAL_STATUSES and job.archive_path:
                archive_path = job.archive_path
                job.archive_path = ""
                job.save(update_fields=("archive_path", "updated_at"))
                schedule_import_archive_unlink(archive_path, job.pk)
                cleared += 1
        PeriodicTaskRun.objects.filter(pk__in=[
            lease_ids[staging_lease_name(job_id)] for job_id in delete_ids
            if staging_lease_name(job_id) in lease_ids
        ]).delete()
        # The post_delete receiver schedules these paths only after this commit.
        TenantImportJob.objects.filter(pk__in=delete_ids).delete()
    return len(delete_ids) + cleared


def cleanup_abandoned_import_objects(*, now=None, batch_size=DEFAULT_CLEANUP_BATCH_SIZE):
    """Roll back a bounded batch of failed/abandoned object journals."""
    batch_size = bounded.limit(batch_size)
    cleanup_at = now or timezone.now()
    if not _claim_named_cleanup_lease(CLEANUP_OBJECTS_LEASE_NAME, cleanup_at):
        return 0
    job_ids = list(
        TenantImportJob.objects.filter(
            Q(status__in=(TenantImportJob.Status.FAILED, TenantImportJob.Status.ABANDONED))
            | Q(
                expires_at__lte=cleanup_at,
                target_makerspace__lifecycle_state__in=("importing", "aborted"),
            ),
            import_objects__state__in=("staged", "promoted", "verified", "failed"),
        )
        .order_by("updated_at", "pk")
        .values_list("pk", flat=True)
        .distinct()[:batch_size]
    )
    from .object_import import rollback_import_objects

    for job in bounded.page(TenantImportJob.objects.filter(pk__in=job_ids).select_related(
        "target_makerspace", "actor"
    ), "import-abandoned-objects"):
        rollback_import_objects(job)
    return len(job_ids)


def resume_expired_finalizing_import_jobs(
    *, now=None, batch_size=DEFAULT_CLEANUP_BATCH_SIZE
):
    """Requeue FINALIZING jobs only when no object promotion lease is live."""
    batch_size = bounded.limit(batch_size)
    sweep_at = now or timezone.now()
    if not _claim_named_cleanup_lease(
        FINALIZATION_SWEEP_LEASE_NAME,
        sweep_at,
        lease_duration=FINALIZATION_SWEEP_LEASE_DURATION,
    ):
        return 0
    live_claims = TenantImportObject.objects.filter(
        job_id=OuterRef("pk"),
        claimed_at__gt=sweep_at - PROMOTION_LEASE_DURATION,
    )
    jobs = list(
        TenantImportJob.objects.filter(
            status=TenantImportJob.Status.FINALIZING,
            actor_id__isnull=False,
        )
        .annotate(has_live_claim=Exists(live_claims))
        .filter(has_live_claim=False)
        .order_by("updated_at", "pk")
        .values("pk", "actor_id")[:batch_size]
    )
    from .tasks import run_import_job_task

    failures = 0
    for job in bounded.items(jobs):
        try:
            dispatch(run_import_job_task, str(job["pk"]), job["actor_id"])
        except Exception:
            failures += 1
            logger.exception(
                "tenant_import_finalization_recovery_failed",
                extra={"tenant_import_job_id": str(job["pk"])},
            )
    if failures:
        logger.error(
            "tenant_import_finalization_recovery_batch_failed",
            extra={"candidate_count": len(jobs), "failure_count": failures},
        )
    return len(jobs)


def resume_stale_pending_import_jobs(*, now=None, batch_size=DEFAULT_CLEANUP_BATCH_SIZE):
    """Recover accepted uploads whose dispatch or staging worker was interrupted."""
    from .services_import_staging import STAGING_LEASE_DURATION, staging_lease_name
    from .tasks import stage_import_job_task

    batch_size = bounded.limit(batch_size)
    sweep_at = now or timezone.now()
    if not _claim_named_cleanup_lease(
        STAGING_SWEEP_LEASE_NAME, sweep_at,
        lease_duration=FINALIZATION_SWEEP_LEASE_DURATION,
    ):
        return 0
    live_claims = PeriodicTaskRun.objects.filter(
        name=Concat(Value(staging_lease_name("")), Cast(OuterRef("pk"), CharField())),
        last_run_at__gt=sweep_at - STAGING_LEASE_DURATION,
    )
    jobs = list(
        TenantImportJob.objects.filter(
            status=TenantImportJob.Status.PENDING, expires_at__gt=sweep_at,
            actor_id__isnull=False, created_at__lt=sweep_at - timedelta(minutes=2),
        ).annotate(has_live_claim=Exists(live_claims)).filter(has_live_claim=False)
        .order_by("created_at", "pk").values("pk", "actor_id")[:batch_size]
    )
    failures = 0
    for job in bounded.items(jobs):
        try:
            dispatch(stage_import_job_task, str(job["pk"]), job["actor_id"])
        except Exception:
            failures += 1
            logger.exception(
                "tenant_import_staging_recovery_failed",
                extra={"tenant_import_job_id": str(job["pk"])},
            )
    if failures:
        logger.error(
            "tenant_import_staging_recovery_batch_failed",
            extra={"candidate_count": len(jobs), "failure_count": failures},
        )
    return len(jobs)


def resume_stalled_materializations(*, now=None, batch_size=DEFAULT_CLEANUP_BATCH_SIZE):
    """Re-run persisted run requests whose execution lock is free.

    Without a broker this sweep is the only executor; with one it recovers a run
    whose lock connection was lost before commit. run_import_job re-takes the lock
    and a fresh attempt token, so a redundant dispatch never starts a second run.
    """
    from .import_run_lock import import_run_lock
    from .tasks import run_import_job_task

    batch_size = bounded.limit(batch_size)
    sweep_at = now or timezone.now()
    if not _claim_named_cleanup_lease(
        MATERIALIZATION_SWEEP_LEASE_NAME, sweep_at,
        lease_duration=FINALIZATION_SWEEP_LEASE_DURATION,
    ):
        return 0
    jobs = list(
        TenantImportJob.objects.filter(
            status=TenantImportJob.Status.MATERIALIZING,
            target_makerspace__isnull=True,
            updated_at__lt=sweep_at - MATERIALIZATION_RESUME_GRACE,
        ).exclude(run_request={}).order_by("updated_at", "pk")
        .values("pk", "run_request")[:batch_size]
    )
    dispatched = 0
    for job in bounded.items(jobs):
        try:
            # A live run holds the lock; skip it rather than queue a no-op.
            with import_run_lock(job["pk"]) as probe:
                free = probe.acquired
            if not free:
                continue
            request = job["run_request"]
            dispatch(run_import_job_task,
                str(job["pk"]), request.get("actor_id"), request.get("target_identity"),
            )
            dispatched += 1
        except Exception:
            logger.exception(
                "tenant_import_materialization_recovery_failed",
                extra={"tenant_import_job_id": str(job["pk"])},
            )
    return dispatched


@transaction.atomic
def _claim_named_cleanup_lease(name, now, *, lease_duration=CLEANUP_LEASE_DURATION):
    row, created = PeriodicTaskRun.objects.select_for_update().get_or_create(
        name=name,
        defaults={"last_run_at": now},
    )
    if not created and now - row.last_run_at < lease_duration:
        return False
    if not created:
        row.last_run_at = now
        row.save(update_fields=("last_run_at",))
    return True
