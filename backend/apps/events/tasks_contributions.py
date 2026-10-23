"""Recover committed contributor work without relying on broker enqueue success."""
import logging

from celery import shared_task
from django.utils import timezone

from apps.makerspaces.models import Makerspace
from apps.makerspaces.platform import feature_enabled
from apps.makerspaces.servability import servable_queryset
from apps.separability.registry import runtime_active
from apps.tenant_migration.gate_runtime import fanout_tenant_write

logger = logging.getLogger(__name__)


def _attempt(callback, counts, **kwargs):
    try:
        callback(**kwargs)
        counts["processed"] += 1
    except Exception:
        counts["failed"] += 1
        logger.exception("event_contributor_maintenance_failed", extra={
            "callback": callback.__name__, "identity": kwargs,
        })


def maintain_tenant(space, counts):
    from .contributions.models_notices import EventContributorNotice
    from .contributions.notifications import deliver_one as contribution
    from .mentoring.help_expiry import expire
    from .mentoring.models_queue import EventHelpRequest
    from .mentoring.models_rounds import MentorNotificationIntent
    from .mentoring.notifications import deliver_one as help_notice, escalate

    now = timezone.now()
    # Expiry removes authority even after a feature is disabled. The domain
    # service rechecks the event/module and owns all audit/lease transitions.
    event_ids = EventHelpRequest.objects.filter(makerspace=space,
        state__in=("open", "claimed")).order_by("event_id").values_list("event_id", flat=True).distinct()
    for event_id in event_ids.iterator(chunk_size=100):
        _attempt(expire, counts, event_id=event_id, limit=100)
        if feature_enabled(space, "events.mentoring"):
            _attempt(escalate, counts, event_id=event_id)
    for model, callback in ((EventContributorNotice, contribution), (MentorNotificationIntent, help_notice)):
        rows = model.objects.filter(makerspace=space, delivered_at__isnull=True,
            available_at__lte=now, attempts__lt=15).order_by("available_at", "pk")
        for notice_id in rows.values_list("pk", flat=True)[:100]:
            _attempt(callback, counts, **{"notice_id" if model is EventContributorNotice else "intent_id": notice_id})


@shared_task
def sweep_contributor_maintenance_task():
    counts = {"processed": 0, "failed": 0, "skipped": 0}
    if not runtime_active("events"):
        return counts
    spaces = servable_queryset(Makerspace.objects.filter(enabled_modules__contains=["events"]))
    for space in spaces.order_by("pk").iterator(chunk_size=100):
        with fanout_tenant_write(space.pk, operation="event_contributor_maintenance", counts=counts) as allowed:
            if not allowed:
                continue
            maintain_tenant(space, counts)
    return counts
