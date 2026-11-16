"""Daily event-storage reconciliation (G11).

Two repairs, both under the owning event's retention lock and both audited:

1. **Usage drift.** `EventAssetUsage.used_bytes/reserved_bytes` is recomputed from the
   live asset rows (team and participant assets not yet deleted). A mismatch is corrected
   and recorded as `event.asset_usage_reconciled` with the before/after numbers.
2. **Imported allowance, exactly once.** Assets that arrived by tenant import carry
   charged bytes but no deployment `EventAssetObligation`, so the target pool never
   counted them. Once target accounting is installed, each such asset is adopted into
   the pool once: reserve then charge through `EventAssetStoragePool` (the managed 25 GB
   decimal cap logic is unchanged). The obligation row is the idempotency key.
"""

import logging

from celery import shared_task
from django.db.models import Sum

from apps.audit.services import record
from apps.operations.cloud_jobs import bounded
from apps.separability.registry import runtime_active

logger = logging.getLogger(__name__)


def _live_totals(event_id):
    from .models_assets import HackathonParticipantAsset, SubmissionAsset
    reserved = used = 0
    for model in (SubmissionAsset, HackathonParticipantAsset):
        sums = model.objects.filter(event_id=event_id, deleted_at__isnull=True).aggregate(
            r=Sum("reserved_bytes"), c=Sum("charged_bytes"))
        reserved += sums["r"] or 0
        used += sums["c"] or 0
    return reserved, used


def _adopt_imported(event):
    """Charge imported, already-stored assets to the target pool once."""
    from apps.makerspaces.storage_events_programme import EventAssetStoragePool
    from .models_assets import EventAssetObligation, HackathonParticipantAsset, SubmissionAsset
    adopted = 0
    known = EventAssetObligation.objects.values("asset_uuid")
    for model in (SubmissionAsset, HackathonParticipantAsset):
        rows = model.objects.filter(event_id=event.pk, deleted_at__isnull=True, charged_bytes__gt=0,
                                    reserved_bytes=0).exclude(public_id__in=known).order_by("pk")[:100]
        for asset in rows:
            pool = EventAssetStoragePool()
            pool.apply_locked(event=event, asset_uuid=asset.public_id, operation="reserve", bytes=asset.charged_bytes)
            pool.apply_locked(event=event, asset_uuid=asset.public_id, operation="charge", bytes=asset.charged_bytes)
            adopted += 1
    return adopted


def reconcile_event(event_id):
    from apps.events.tasks_retention import _retention_event
    from .models_assets import EventAssetUsage
    with _retention_event(event_id) as event:
        usage = EventAssetUsage.objects.select_for_update().filter(event=event).first()
        adopted = _adopt_imported(event)
        if usage is None:
            return {"changed": False, "adopted": adopted}
        reserved, used = _live_totals(event.pk)
        before = {"reserved_bytes": usage.reserved_bytes, "used_bytes": usage.used_bytes}
        changed = (usage.reserved_bytes, usage.used_bytes) != (reserved, used)
        if changed:
            usage.reserved_bytes, usage.used_bytes = reserved, used
            usage.save(update_fields=["reserved_bytes", "used_bytes"])
        if changed or adopted:
            record(None, "event.asset_usage_reconciled", makerspace=event.makerspace, target=usage,
                   meta={"before": before, "after": {"reserved_bytes": reserved, "used_bytes": used},
                         "imported_assets_adopted": adopted})
        return {"changed": changed, "adopted": adopted}


@shared_task
def reconcile_event_storage_task():
    counts = {"reconciled": 0, "failed": 0, "skipped": 0}
    if not runtime_active("events"):
        return counts
    from apps.makerspaces.servability import servable_queryset
    from apps.events.models import Event
    from .models_assets import EventAssetUsage
    from apps.makerspaces.scheduled_scope import live_space_ids
    spaces = servable_queryset().filter(pk__in=live_space_ids("events")).values("pk")
    rows = (EventAssetUsage.objects.filter(event__makerspace__in=spaces).order_by("event_id")
            .values_list("event_id", flat=True))
    for event_id in bounded.items(list(rows[:500])):
        try:
            if Event.objects.filter(pk=event_id).exists():
                reconcile_event(event_id)
                counts["reconciled"] += 1
        except Exception:
            counts["failed"] += 1
            logger.warning("event_storage_reconcile_failed", extra={"event_id": event_id})
    return counts
