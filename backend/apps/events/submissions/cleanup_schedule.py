"""Lifecycle-owned sweeper hooks, evaluated from event clocks under G locks."""
from datetime import timedelta
from django.db.models import Q
from django.utils import timezone
from apps.audit.services import record

from .models_assets import SubmissionAsset, HackathonParticipantAsset, SubmissionAssetWork


def enqueue_abandoned_locked(*, event, actor=None, now=None):
    now = now or timezone.now()
    for cls in (SubmissionAsset, HackathonParticipantAsset):
        candidates = cls.objects.select_for_update().filter(event=event, deleted_at__isnull=True)
        abandoned = Q(state__in=["reserved", "uploading"], last_activity_at__lt=now-timedelta(hours=24))
        if cls is SubmissionAsset and now >= event.ends_at + timedelta(days=30):
            from .models_projects import SnapshotAsset
            referenced = SnapshotAsset.objects.values("asset_id")
            unattached = cls.objects.exclude(pk__in=referenced).filter(event=event).values("pk")
            abandoned |= Q(pk__in=unattached, state__in=["reserved", "uploading", "ready", "rejected", "aborted"])
        for asset in candidates.filter(abandoned).order_by("pk"):
            asset.state, asset.expired_at = "aborted", asset.expired_at or now
            asset.version += 1
            asset.save(update_fields=["state", "expired_at", "version"])
            work = asset.work
            work.state, work.next_attempt_at, work.lease_token, work.lease_until = "pending", now, None, None
            work.save()
            record(actor, "event.asset_abandoned", makerspace=event.makerspace, target=asset,
                   meta={"bytes": asset.declared_bytes})


def due_work_ids(*, now=None, limit=100):
    """Selection only. AssetJob's lease CAS decides which worker executes.

    Do not filter by enabled feature/module or user standing: metadata and
    cleanup outlive those permissions. G's always-present locator registry calls
    this equivalently under tombstoning or its external scheduler.
    """
    now = now or timezone.now()
    return tuple(SubmissionAssetWork.objects.filter(next_attempt_at__lte=now,
        state__in=["pending", "verify_absence", "processing"]).filter(
        Q(lease_until__isnull=True) | Q(lease_until__lte=now)
    ).order_by("next_attempt_at", "pk").values_list("pk", flat=True)[:limit])
