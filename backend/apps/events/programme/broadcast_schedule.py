"""DB deadlines are authoritative; broker timers are only a delivery hint."""

from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, Throttled, ValidationError

from apps.audit.services import record
from apps.events.broadcasts import authorize
from apps.events.models_broadcasts import EventBroadcast, EventBroadcastPreview
from apps.events.services_broadcasts import locked_event
from apps.integrations.broadcasts_worker import enqueue, recover_for_tenants

from .broadcast_preview import audience_proof, campaign_command, content_digest
from .commands import ProgrammeConflict


def cancel_composer(campaign, actor, payload):
    def cancel(row, locked_actor):
        if row.render_schema_version != 2:
            raise ValidationError("Use the legacy cancellation action for this campaign.")
        from apps.events.services_broadcasts import cancel_locked
        row = cancel_locked(row, locked_actor)
        return {"campaign_id": row.pk, "state": row.status, "version": row.version}
    campaign_command(campaign, actor, "broadcast.cancel", payload, cancel)
    result = EventBroadcast.objects.get(pk=campaign.pk, event_id=campaign.event_id)
    authorize(result, actor)
    return result


def schedule(campaign, actor, payload):
    def confirm(row, locked_actor):
        if row.status != "draft" or row.render_schema_version != 2:
            raise ProgrammeConflict("invalid_transition", "Only a composer draft can be scheduled.")
        if payload["confirm"] is not True:
            raise ValidationError({"confirm": "Confirm the selected audience before sending."})
        now = timezone.now()
        if payload["available_at"] < now + timedelta(seconds=5):
            raise ValidationError({"available_at": "Choose a send time at least five seconds from now."})
        preview = EventBroadcastPreview.objects.filter(pk=payload["preview_id"], campaign=row,
                                                        created_by=locked_actor).first()
        count, revision = audience_proof(row)
        if (preview is None or preview.content_sha256 != content_digest(row)
                or payload["revision"] != preview.revision or revision != preview.revision
                or payload["recipient_count"] != preview.recipient_count or count != preview.recipient_count):
            raise ProgrammeConflict("stale_version", "The audience or event changed. Preview it again.")
        if EventBroadcast.objects.filter(makerspace=row.makerspace,
                queued_at__gte=now - timedelta(hours=1)).count() >= 10:
            raise Throttled(detail="Limit of 10 broadcasts per hour for this makerspace.")
        row.status = "scheduled"
        row.available_at = payload["available_at"]
        row.confirmed_preview = preview
        row.queued_at = now
        row.version += 1
        row.save(update_fields=["status", "available_at", "confirmed_preview", "queued_at", "version", "updated_at"])
        record(locked_actor, "event.broadcast.scheduled", makerspace=row.makerspace,
               target=row, meta={"count": count, "preview_id": preview.pk, "version": row.version})
        return {"campaign_id": row.pk, "state": row.status, "version": row.version}
    campaign_command(campaign, actor, "broadcast.schedule", payload, confirm)
    result = EventBroadcast.objects.get(pk=campaign.pk, event_id=campaign.event_id)
    authorize(result, actor)
    return result


@transaction.atomic
def release_due(campaign_id):
    candidate = EventBroadcast.objects.filter(pk=campaign_id).first()
    if candidate is None:
        return
    event = locked_event(candidate.event, candidate.created_by)
    row = EventBroadcast.objects.select_for_update().get(pk=candidate.pk, event=event)
    row.event = event
    row.makerspace = event.makerspace
    if row.status != "scheduled" or row.available_at is None or row.available_at > timezone.now():
        return
    try:
        authorize(row, row.created_by)
    except APIException:
        row.status, row.completed_at = "cancelled", timezone.now()
    else:
        row.status = "queued"
        transaction.on_commit(lambda: enqueue("event_broadcast", row.pk))
    row.version += 1
    row.save(update_fields=["status", "completed_at", "version", "updated_at"])
    record(None, f"event.broadcast.{row.status}", makerspace=row.makerspace, target=row,
           meta={"version": row.version})


@shared_task
def resume_scheduled_broadcasts():
    """G wires this task to periodic recovery; it also works after enqueue loss."""
    due = EventBroadcast.objects.filter(status="scheduled", available_at__lte=timezone.now())
    rows = list(due.order_by("available_at", "pk").values_list("makerspace_id", "pk")[:200])
    counts = {"skipped": 0}
    recover_for_tenants(((space_id, (pk,)) for space_id, pk in rows),
        operation="event_broadcast_schedule", counts=counts, callback=release_due)
    return counts
