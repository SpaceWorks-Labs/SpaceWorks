"""Cloud programme task wrappers; domain services retain authority and leases.

No eager recursion and no unbounded event discovery. Free HTTP ticks use separately
installed ChunkContext adapters, never these full-profile wrappers.
"""
import logging

from celery import shared_task
from django.conf import settings

from apps.operations.cloud_jobs.contracts import JobsUnavailable
from apps.tenant_migration.gate_runtime import fanout_tenant_write

logger = logging.getLogger(__name__)


def _full_limit(limit):
    if getattr(settings, "SPACEWORKS_DEPLOYMENT_PROFILE", "full") == "free":
        raise JobsUnavailable("bounded_tick_adapter_required")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("Programme batch limit must be in 1..100")
    return limit


def _failed(key, counts):
    if counts.get("failed"):
        logger.warning("cloud_programme_chunk_failed", extra={"task_key": key, **counts})
        raise JobsUnavailable("programme_chunk_failed")
    return counts


@shared_task
def process_asset_work_task(limit=25):
    limit = _full_limit(limit)
    from .submissions.api_runtime import runtime
    from .submissions.asset_jobs import AssetJob
    from .submissions.cleanup_schedule import due_work_ids
    from .submissions.models_assets import SubmissionAssetWork
    config = runtime()
    counts = {"processed": 0, "failed": 0, "skipped": 0}
    for work_id in due_work_ids(limit=limit):
        work = SubmissionAssetWork.objects.filter(pk=work_id).first()
        if work is None:
            continue
        # Nullable FK reads deliberately do not use select_for_update/select_related.
        participant = work.participant_asset_id is not None
        asset = work.participant_asset if participant else work.asset
        with fanout_tenant_write(asset.event.makerspace_id, operation="event_asset_work", counts=counts) as allowed:
            if not allowed:
                continue
            try:
                job = AssetJob(actor=None, event_id=asset.event_id,
                               team_id=None if participant else asset.team_id,
                               asset_id=asset.pk, participant=participant, storage=config.storage)
                job.run(scan_options=config.scan_options, sandbox_command=config.sandbox_command)
                counts["processed"] += 1
            except Exception:
                # The domain job owns retry/lease recovery; don't release its token.
                counts["failed"] += 1
    return _failed("event-asset-work", counts)


@shared_task
def sweep_asset_lifecycle_task(limit=25):
    limit = _full_limit(limit)
    from .cloud_runtime import runtime
    return runtime().asset_lifecycle(limit=limit)


@shared_task
def resume_certificates_task(limit=25):
    limit = _full_limit(limit)
    from .certificates.batches import run_chunk
    from .certificates.models import CertificateIssueBatch
    from .certificates.lifecycle import render_certificate
    from .models_certificates import EventAttendanceCertificate
    from django.db.models import Q
    from django.utils import timezone
    from datetime import timedelta
    counts = {"processed": 0, "failed": 0, "skipped": 0}
    # One issuance chunk per batch; never process_batch.delay() eager recursion.
    from apps.makerspaces.scheduled_scope import live_space_ids
    live = live_space_ids("events")  # no certificate work while events is off (#183B)
    batches = CertificateIssueBatch.objects.filter(state__in=("queued", "running"),
                                                   event__makerspace_id__in=live).order_by("pk")[:limit]
    for batch in batches:
        with fanout_tenant_write(batch.event.makerspace_id, operation="event_certificate_resume", counts=counts) as allowed:
            if not allowed:
                continue
            try:
                run_chunk(batch.pk)
            except Exception:
                counts["failed"] += 1
    pending = Q(status__in=("pending", "failed")) | Q(
        status="rendering", render_started_at__lte=timezone.now()-timedelta(minutes=5),
    ) | Q(status="rendering", render_started_at__isnull=True)
    rows = EventAttendanceCertificate.objects.filter(pending, event__makerspace_id__in=live).order_by(
        "render_attempts", "issued_at", "pk")[:limit]
    for certificate in rows:
        with fanout_tenant_write(certificate.event.makerspace_id, operation="event_certificate_resume", counts=counts) as allowed:
            if not allowed:
                continue
            try:
                render_certificate(certificate)
                counts["processed"] += 1
            except Exception:
                counts["failed"] += 1
    return _failed("event-certificate-resume", counts)


@shared_task
def cleanup_print_jobs_task(limit=25):
    limit = _full_limit(limit)
    from .certificates.print_cleanup import cleanup_expired
    return cleanup_expired(limit=limit)


@shared_task
def cleanup_programme_receipts_task(limit=25):
    limit = _full_limit(limit)
    from .cloud_runtime import runtime
    return runtime().programme_receipts(limit=limit, retention_days=30)


@shared_task
def sweep_stage_file_retention_task(limit=25):
    limit = _full_limit(limit)
    from .cloud_runtime import runtime
    return runtime().stage_file_retention(limit=limit)
