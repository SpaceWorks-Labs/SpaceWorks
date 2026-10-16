"""Bounded, per-tenant expiry and recoverable reminder sweeps."""
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
from .models import PresenceSession
from .notifications import remind
from .policy import require_enabled

logger = logging.getLogger(__name__)


def sweep_presence(*, now=None, batch_size=200):
    now = now or timezone.now()
    counts = {"expired": 0, "reminded": 0, "skipped": 0, "failed": 0}
    due = PresenceSession.objects.filter(expires_at__lte=now).filter(
        Q(ended_at=None) | Q(end_reason="expired", expiry_reminded_at=None))
    spaces = servable_queryset(Makerspace.objects.filter(pk__in=due.values("makerspace_id"))).order_by("pk")
    for space in spaces.iterator():
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
                    for row in rows:
                        if row.ended_at is None:
                            row.ended_at, row.end_reason = row.expires_at, "expired"
                            row.save(update_fields=["ended_at", "end_reason"])
                            audit.record(None, "presence.expired", makerspace=space, target=row)
                            counts["expired"] += 1
                        if row.expiry_reminded_at is None:
                            try:
                                with transaction.atomic():
                                    fresh = row.expires_at >= now - timedelta(minutes=10)
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
