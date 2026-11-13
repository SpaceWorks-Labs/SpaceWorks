"""Bounded, per-tenant expiry and recoverable reminder sweeps."""
from apps.operations.cloud_jobs import bounded

import logging
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.audit import services as audit
from apps.makerspaces.models import Makerspace
from apps.makerspaces.servability import servable_queryset
from apps.tenant_migration.gate_runtime import fanout_tenant_write
from .event_attendance import ended_event_registrations, event_end_times
from .models import PresenceSession
from .notifications import remind
from .policy import require_enabled

logger = logging.getLogger(__name__)


def sweep_presence(*, now=None, batch_size=200):
    batch_size = bounded.limit(batch_size)
    now = now or timezone.now()
    counts = {"expired": 0, "reminded": 0, "skipped": 0, "failed": 0}
    # An event check-in also closes once its event has ended, even when the event
    # was shortened after check-in and the session's own expiry is still ahead.
    due = PresenceSession.objects.filter(
        Q(expires_at__lte=now, ended_at=None) | Q(expires_at__lte=now, end_reason="expired", expiry_reminded_at=None)
        | Q(ended_at=None, event_registration__in=ended_event_registrations(now)))
    spaces = servable_queryset(Makerspace.objects.filter(pk__in=due.values("makerspace_id"))).order_by("pk")
    for space in bounded.page(spaces, "presence-spaces"):
        try:
            require_enabled(space)
        except Exception:
            continue
        with fanout_tenant_write(space.pk, operation="presence_expiry", counts=counts) as allowed:
            if not allowed:
                continue
            try:
                with transaction.atomic():
                    # Match interactive writers: tenant before session and the
                    # display-generation row touched by save signals.
                    Makerspace.objects.select_for_update(no_key=True).get(pk=space.pk)
                    rows = list(due.filter(makerspace=space).select_for_update(skip_locked=True)
                                .order_by("expires_at", "pk")[:batch_size])
                    event_ends = event_end_times(rows, now)
                    for row in bounded.items(rows):
                        event_end = event_ends.get(row.pk)
                        if row.ended_at is None:
                            ended = row.expires_at if event_end is None else max(
                                row.started_at, min(row.expires_at, event_end))
                            row.ended_at, row.end_reason = ended, "expired"
                            row.save(update_fields=["ended_at", "end_reason"])
                            # Literal meta per call so the audit presentation catalogue sees it.
                            if event_end is None:
                                audit.record(None, "presence.expired", makerspace=space, target=row)
                            else:
                                audit.record(None, "presence.expired", makerspace=space, target=row,
                                             meta={"cause": "event_ended"})
                            counts["expired"] += 1
                        if row.expiry_reminded_at is None:
                            try:
                                with transaction.atomic():
                                    # The event is over, so renewal is refused: never prompt for it.
                                    fresh = event_end is None and row.expires_at >= now - timedelta(minutes=10)
                                    if fresh:
                                        remind(row)
                                    row.expiry_reminded_at = now
                                    row.save(update_fields=["expiry_reminded_at"])
                                    if fresh:
                                        audit.record(None, "presence.expiry_reminded", makerspace=space, target=row)
                                    else:
                                        audit.record(None, "presence.expiry_reminder_skipped", makerspace=space, target=row)
                                counts["reminded"] += int(fresh)
                            except Exception:
                                counts["failed"] += 1
                                logger.warning("presence_reminder_failed", extra={"makerspace_id": space.pk, "session_id": row.pk})
            except Exception:
                counts["failed"] += 1
                logger.warning("presence_expiry_failed", extra={"makerspace_id": space.pk})
    return counts


@shared_task
def expire_presence_sessions_task():
    return sweep_presence()
