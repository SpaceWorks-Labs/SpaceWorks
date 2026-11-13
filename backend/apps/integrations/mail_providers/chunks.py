"""Round-robin durable cursors prevent any mail surface starving another."""
from django.db.models import Q
from django.utils import timezone

from apps.operations.cloud_jobs import bounded
from apps.operations.cloud_jobs.contracts import BudgetExpired, ChunkResult, GuardLost
from .outbox import delivery_deadline, drain

PHASES = ("media", "personal", "mail", "channels", "firebase")


def drain_chunk(context):
    context.check()
    index = context.checkpoint.get("phase", 0)
    if type(index) is not int or not 0 <= index < len(PHASES):
        index = 0
    phase = PHASES[index]
    cursors = dict(context.checkpoint.get("cursors", {}))
    done = set(context.checkpoint.get("done", []))
    processed = 0
    try:
        with bounded.scope(context), delivery_deadline(context.deadline, guard=context.check):
            result = _phase(phase, context, cursors.get(phase, 0))
        processed = result.get("processed", 0)
        cursors[phase] = result.get("cursor", 0)
        if result.get("remaining", False):
            done.discard(phase)
        else:
            done.add(phase)
    except bounded._StopChunk as stop:
        if isinstance(stop.cause, GuardLost):
            raise stop.cause
        done.discard(phase)
    except BudgetExpired:
        done.discard(phase)
    # Always rotate, even when an earlier phase has a continuous backlog. Revisit
    # completed phases too: new mail cannot wait for another surface to go quiet.
    complete = done == set(PHASES)
    checkpoint = {"phase": (index + 1) % len(PHASES), "cursors": cursors, "done": sorted(done)}
    return ChunkResult(complete, {} if complete else checkpoint, processed=processed)


def _phase(phase, context, cursor):
    if phase == "firebase":
        from django.apps import apps
        if not apps.is_installed("apps.notifications"):
            return {"remaining": False, "cursor": 0, "processed": 0}
        from apps.notifications.browser_firebase_delivery import drain_chunk as drain_firebase
        return drain_firebase(context, cursor)
    if phase == "channels":
        from .channel_chunks import drain_channels
        return drain_channels(context, cursor)
    if phase == "media":
        from apps.integrations.notification_media import cleanup_grants
        result = cleanup_grants(limit=min(context.limit, 5), after_id=cursor)
        return {**result, "processed": result["deleted"]}
    if phase == "mail":
        return drain(monotonic_deadline=context.deadline, limit=min(context.limit, 5),
                     guard=context.check, cursor=cursor)
    from apps.integrations.models_contract import NotificationEnvelope
    from apps.integrations.notification_tasks import deliver_envelope
    now = timezone.now()
    rows = NotificationEnvelope.objects.filter(Q(available_at=None) | Q(available_at__lte=now)).filter(
        Q(processed_at=None) | Q(deliveries__state="retrying", deliveries__next_attempt_at__lte=now)
        | Q(deliveries__claim_until__lte=now)).exclude(source_kind="legacy.lifecycle", message_body="").exclude(
        source_kind="legacy.lifecycle", context__free_fanout_state="operator_cancelled")
    ids = list(rows.filter(pk__gt=cursor).order_by("pk").distinct().values_list("pk", flat=True)[:2])
    from apps.tenant_migration.gate_runtime import fanout_tenant_write
    for envelope_id in ids[:1]:  # one envelope per chunk
        context.check()
        envelope = NotificationEnvelope.objects.get(pk=envelope_id)
        with fanout_tenant_write(envelope.makerspace_id, operation="notification_contract_outbox", counts={}) as allowed:
            if not allowed:
                continue
            deliver_envelope(envelope_id)
    if ids:
        context.check()
    remaining = len(ids) > 1
    return {"remaining": remaining, "cursor": ids[0] if remaining else 0, "processed": int(bool(ids))}
