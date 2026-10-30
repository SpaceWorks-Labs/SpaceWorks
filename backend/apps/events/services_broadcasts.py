"""All compose/queue/cancel mutations revalidate under the event and tenant locks."""

from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import Throttled, ValidationError

from apps.audit.services import record
from apps.integrations.broadcasts_templates import validate_strings
from apps.integrations.broadcasts_worker import enqueue
from apps.encryption.write_fence import assert_mapped_write_allowed
from apps.makerspaces.guards import require_module_locked
from apps.tenant_migration.gate_runtime import assert_write_allowed
from .broadcasts import PLACEHOLDERS, authorize
from .models import Event, EventSeries
from .models_broadcasts import EventBroadcast


def locked_event(event, actor=None):
    assert_write_allowed(event.makerspace_id)
    assert_mapped_write_allowed(event.makerspace_id)
    original_space_id = event.makerspace_id
    series_id = Event.objects.values_list("series_id", flat=True).get(pk=event.pk)
    if series_id:
        EventSeries.objects.select_for_update().get(pk=series_id)
    event = Event.objects.select_for_update().get(pk=event.pk)
    if event.makerspace_id != original_space_id or event.series_id != series_id:
        from .programme.commands import ProgrammeConflict
        raise ProgrammeConflict("scope_changed", "The event scope changed. Retry the operation.")
    event.makerspace = require_module_locked(event.makerspace_id, "events")
    event._broadcast_actor = actor
    if actor is not None:
        from .staff_grant_locks import lock_authority
        event._broadcast_actor = lock_authority(actor, event)
    return event


@transaction.atomic
def compose(event, actor, **values):
    event = locked_event(event, actor)
    return compose_locked(event, event._broadcast_actor, values)


def compose_locked(event, actor, values):
    """Caller holds source/fence/event/tenant/authority locks in that order."""
    values = dict(values)
    schema = values.get("render_schema_version", 1)
    ctas = values.pop("ctas", [])
    if schema == 2:
        from .programme.broadcast_content import pack
        from .programme.broadcast_designs import require_design_allowed
        require_design_allowed(event.makerspace, values.get("design", "classic"))
        values["body"] = pack(values.get("subject", ""), values.get("body", ""),
                              ctas=ctas, design=values.get("design", "classic"))
    elif schema != 1 or ctas:
        raise ValidationError({"render_schema_version": "Choose composer version 2 for calls to action."})
    campaign = EventBroadcast(event=event, makerspace=event.makerspace, created_by=actor, **values)
    authorize(campaign, actor)
    # Validate caller input before encrypted persistence.
    if schema == 1:
        validate_strings(values.get("subject", ""), values.get("body", ""), PLACEHOLDERS)
    validate_audience(campaign)
    campaign.save()
    record(actor, "event.broadcast.created", makerspace=event.makerspace, target=campaign)
    return campaign


def validate_audience(campaign):
    from .models import EventRegistration
    if (not isinstance(campaign.statuses, list) or not campaign.statuses
            or set(campaign.statuses) - set(EventRegistration.Status.values)
            or campaign.attendance not in {"any", "attended", "not_attended"}):
        raise ValidationError("Choose valid registration and attendance filters.")


@transaction.atomic
def change(campaign, actor, action):
    event = locked_event(campaign.event, actor)
    actor = event._broadcast_actor
    campaign = EventBroadcast.objects.select_for_update().get(pk=campaign.pk, event=event)
    authorize(campaign, actor)
    if action == "cancel":
        if campaign.render_schema_version == 2:
            raise ValidationError("Use the versioned composer cancellation command.")
        return cancel_locked(campaign, actor)
    if action == "queue":
        if campaign.render_schema_version == 2:
            raise ValidationError("Preview and confirm this composer campaign before scheduling it.")
        if campaign.status != "draft":
            raise ValidationError("Only drafts can be queued.")
        if EventBroadcast.objects.filter(makerspace=event.makerspace,
                queued_at__gte=timezone.now() - timedelta(hours=1)).count() >= 10:
            raise Throttled(detail="Limit of 10 broadcasts per hour for this makerspace.")
        campaign.status, campaign.queued_at = "queued", timezone.now()
    else:
        raise ValidationError("This campaign cannot be changed in its current state.")
    campaign.version += 1
    campaign.save(update_fields=["status", "queued_at", "completed_at", "updated_at", "version"])
    record(actor, f"event.broadcast.{campaign.status}", makerspace=event.makerspace, target=campaign)
    if action == "queue":
        transaction.on_commit(lambda: enqueue("event_broadcast", campaign.pk))
    return campaign


def cancel_locked(campaign, actor):
    """Caller holds source/fence/event/tenant/authority/campaign locks."""
    authorize(campaign, actor)
    if campaign.status == "cancelled":
        return campaign
    if campaign.status not in {"draft", "scheduled", "queued", "sending"}:
        raise ValidationError("This campaign cannot be changed in its current state.")
    now = timezone.now()
    # The undo: a "send now" stopped before its five-second hold elapsed. After the hold
    # this is an ordinary cancel, which stops only unclaimed sends.
    in_hold = (campaign.undo_hold and campaign.status == "scheduled"
               and campaign.available_at is not None and now < campaign.available_at)
    campaign.status, campaign.completed_at = "cancelled", now
    campaign.version += 1
    campaign.save(update_fields=["status", "completed_at", "version", "updated_at"])
    record(actor, "event.broadcast_cancelled_in_hold" if in_hold else "event.broadcast.cancelled",
           makerspace=campaign.makerspace, target=campaign)
    return campaign
