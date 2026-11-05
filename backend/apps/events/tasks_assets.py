"""Bounded scans, deadline locks and retained expiry/cleanup recovery."""
import logging

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from apps.events.certificate_storage import _client
from apps.events.tasks_retention import _retention_event
from apps.events.tasks_sweeps import batch, take_ids
from apps.operations.cloud_jobs import bounded
from apps.makerspaces import limits
from apps.separability.registry import runtime_active

logger = logging.getLogger(__name__)


def retained_storage():
    from .submissions.storage import EventAssetStorage
    client = _client(settings.AWS_S3_ENDPOINT_URL)
    return EventAssetStorage(client, client, settings.AWS_STORAGE_BUCKET_NAME)


@shared_task
def sweep_asset_work_task():
    from .submissions.cleanup_schedule import due_work_ids
    from .submissions.models_assets import SubmissionAssetWork
    from .submissions.retention_jobs import TERMINAL, cleanup_asset
    from .submissions.asset_jobs import AssetJob
    counts = {"processed": 0, "failed": 0}
    for pk in bounded.items(due_work_ids(limit=batch(100, heavy=True))):
        try:
            work = SubmissionAssetWork.objects.get(pk=pk)
            participant = work.participant_asset_id is not None
            asset = work.participant_asset if participant else work.asset
            if asset.state in TERMINAL | {"ready"}:
                cleanup_asset(asset_id=asset.pk, participant=participant, storage=retained_storage())
            elif runtime_active("events"):
                from .submissions.api_runtime import runtime
                active = runtime()  # Missing scanner/provider configuration fails closed.
                # Initial uploads require a request to obtain their write descriptor.
                # A lost initializing request remains resumable, then idle cleanup wins.
                if asset.state == "reserved":
                    continue
                AssetJob(actor=asset.uploaded_by, event_id=asset.event_id,
                    team_id=getattr(asset, "team_id", None), asset_id=asset.pk,
                    participant=participant, storage=active.storage).run(
                        scan_options=active.scan_options, sandbox_command=active.sandbox_command)
            counts["processed"] += 1
        except Exception:
            counts["failed"] += 1
            logger.warning("event_asset_work_deferred", extra={"work_id": pk})
    return counts


@shared_task
def sweep_asset_deadlines_task():
    from .submissions.deadlines import lock_event_submissions
    from .hackathons.admission_models import HackathonConfig
    if not runtime_active("events"):
        return 0
    ids = take_ids("asset-deadlines", HackathonConfig.objects.filter(
        enabled=True, submission_deadline__lte=timezone.now()), limit=batch(100))
    done = 0
    for config in bounded.items(HackathonConfig.objects.filter(pk__in=ids)):
        try:
            done += lock_event_submissions(event_id=config.event_id, limit=100)
        except Exception:
            logger.warning("event_asset_deadline_deferred", extra={"event_id": config.event_id})
    from .submissions.stage_notices import remind_due_stages  # #178: stage deadline reminders ride this sweep.
    remind_due_stages()
    return done


@shared_task
def sweep_asset_retention_task():
    from .submissions.models_assets import EventAssetUsage
    from .submissions.retention import anchor_locked, expire_locked
    from .submissions.cleanup_schedule import enqueue_abandoned_locked, rebuild_cleanup_work_locked
    from .submissions.ports import SubmissionContext
    from .submissions.quota import usage_locked
    ids = take_ids("asset-retention", EventAssetUsage.objects.all(), limit=batch(100, heavy=True))
    done = 0
    for usage in bounded.items(EventAssetUsage.objects.filter(pk__in=ids)):
        try:
            with _retention_event(usage.event_id) as event:
                ctx = SubmissionContext(event=event, team_id=None, member_ids=(), leader_id=None,
                    deadline=event.ends_at, managed=not limits.is_self_host())
                locked = usage_locked(ctx)
                if locked.expires_at is None and event.ends_at <= timezone.now():
                    anchor_locked(event=event, usage=locked, actor=None, kind="fallback", at=event.ends_at)
                enqueue_abandoned_locked(event=event, limit=100)
                expire_locked(event=event, actor=None, limit=100)
                rebuild_cleanup_work_locked(event=event, limit=100)
            done += 1
        except Exception:
            logger.warning("event_asset_retention_deferred", extra={"event_id": usage.event_id})
    return done


@shared_task
def reconcile_asset_obligations_task():
    from .submissions.obligations import sweep
    return sweep(storage=retained_storage(), limit=batch(100, heavy=True))
