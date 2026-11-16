"""Durable event deadlines. G calls these under lifecycle locks, even tombstoned."""
from datetime import timedelta

from django.utils import timezone
from apps.audit.services import record

from .errors import SubmissionError
from .models_assets import SubmissionAsset, HackathonParticipantAsset, SubmissionAssetWork


def anchor_locked(*, event, usage, actor, kind, at):
    if kind not in {"results", "fallback", "cancelled"}:
        raise SubmissionError("invalid_retention_anchor")
    if kind == "results":
        if usage.first_results_published_at:
            return usage.expires_at
        usage.first_results_published_at = at
    elif usage.retention_anchor_kind in {"results", "cancelled"}:
        return usage.expires_at
    deadline = at + timedelta(days=365)
    # Earlier results replace the fallback. Corrections and later uploads do not
    # extend an established schedule, even after import or a results amendment.
    if usage.expires_at:
        deadline = min(deadline, usage.expires_at)
    usage.retention_anchor, usage.retention_anchor_kind, usage.expires_at = at, kind, deadline
    usage.save(update_fields=["first_results_published_at", "retention_anchor", "retention_anchor_kind", "expires_at"])
    for cls in (SubmissionAsset, HackathonParticipantAsset):
        cls.objects.filter(event=event).update(expires_at=deadline)
    record(actor, "event.asset_retention_anchored", makerspace=event.makerspace, target=usage,
           meta={"kind": kind, "expires_at": deadline.isoformat()})
    return deadline


def expire_locked(*, event, actor, at=None, limit=100):
    at = at or timezone.now()
    for cls in (SubmissionAsset, HackathonParticipantAsset):
        rows = cls.objects.select_for_update().filter(event=event, expires_at__lte=at, expired_at__isnull=True)
        for asset in rows.order_by("pk")[:min(max(limit, 1), 500)]:
            asset.expired_at, asset.state = at, "expiring"
            asset.expired_size_bytes = asset.actual_bytes
            asset.version += 1
            asset.save(update_fields=["expired_at", "state", "expired_size_bytes", "version"])
            work, _ = SubmissionAssetWork.objects.get_or_create(**{
                "participant_asset" if cls is HackathonParticipantAsset else "asset": asset})
            work.state, work.next_attempt_at, work.lease_token, work.lease_until = "pending", at, None, None
            work.save()
            record(actor, "event.asset_expired", makerspace=event.makerspace, target=asset,
                   meta={"sha256": asset.sha256, "bytes": asset.actual_bytes})


def capture_disposition(asset, *, now=None):
    """Expected absent expires; missing ready/unexpired bytes remain corruption."""
    now = now or timezone.now()
    if asset.state == "expired" and asset.expired_at:
        return "expected_expired"
    if asset.state == "expired":
        return "invalid_retention_state"
    if asset.state == "ready" and asset.expired_at:
        return "invalid_retention_state"
    if asset.state in {"expiring", "deleting"}:
        return "retry_cleanup"
    if asset.state == "ready" and asset.expires_at and asset.expires_at <= now:
        return "retention_finalization_required"
    return "required" if asset.state == "ready" else "pending"
