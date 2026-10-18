"""Clock enforcement for help claims; GETs never mutate queue state."""
from datetime import timedelta
from uuid import uuid4
from django.db import transaction
from apps.events.services_write_boundary import write_boundary
from django.db.models import Q
from django.utils import timezone
from apps.audit.services import record
from apps.events.models import Event
from apps.events.contributions import commands
from apps.events.contributions.errors import ProgrammeError
from apps.events.contributions.ports import ports
from apps.makerspaces.guards import require_module_locked
from apps.tenant_migration.gate_runtime import boundary_tenant_write
from .models_queue import EventHelpRequest, EventHelpAction


def deadline(row, event):
    return min(event.ends_at, row.expires_at or event.ends_at)


def live_claim(row, at=None):
    return row.state == "claimed" and row.claim_expires_at is not None and row.claim_expires_at > (at or timezone.now())


def require_live(row, event):
    if deadline(row, event) <= timezone.now() or row.state == "expired":
        raise ProgrammeError("help_expired", "This help request expired.")
    if row.state == "claimed" and not live_claim(row):
        raise ProgrammeError("lease_lost", "This help claim expired. Refresh the queue.")


def claim_values(row, event, now):
    return {"claim_uuid": uuid4(), "claim_generation": row.claim_generation + 1,
        "claim_expires_at": min(deadline(row, event), now + timedelta(minutes=row.type.claim_minutes))}


def release_locked(*, row, event, actor=None, kind="lease_expired", terminal=False):
    from .help_workflow import notice_locked
    commands.changed(row, state="expired" if terminal else "open", claimed_by=None,
        claim_uuid=None, claim_expires_at=None, last_opened_at=timezone.now(), open_generation=row.open_generation + 1)
    commands.new_row(EventHelpAction, event, request=row, actor=actor, kind=kind)
    record(actor, f"event.help.{kind}", makerspace=event.makerspace, target=row,
           meta={"event_id": event.pk, "version": row.version})
    notice_locked(row, event, kind)


def expire(*, event_id, limit=100):
    """G schedules this source-fenced, idempotent maintenance hook each minute.

    Expiry remains available with the feature disabled: it only removes authority.
    No account/key rows or provider calls are made inside the event transaction.
    """
    adapter = ports()
    seed = Event.objects.get(pk=event_id)
    adapter.prepare_private_write(makerspace_id=seed.makerspace_id)
    with write_boundary(seed):
        with transaction.atomic():
            event = Event.objects.select_for_update().get(pk=event_id)
            event.makerspace = require_module_locked(event.makerspace_id, "events")
            now, count = timezone.now(), 0
            rows = EventHelpRequest.objects.select_for_update().filter(event=event,
                state__in=["open", "claimed"]).filter(Q(expires_at__lte=now) | Q(event__ends_at__lte=now)
                | Q(state="claimed", claim_expires_at__lte=now)
                | Q(state="claimed", claim_expires_at__isnull=True)).order_by("pk")[:min(max(limit, 1), 100)]
            for row in rows:
                terminal = deadline(row, event) <= now
                if terminal or row.state == "claimed" and not live_claim(row, now):
                    release_locked(row=row, event=event, terminal=terminal,
                        kind="expired" if terminal else "lease_expired")
                    count += 1
                    if count >= min(max(limit, 1), 100):
                        break
            return count
