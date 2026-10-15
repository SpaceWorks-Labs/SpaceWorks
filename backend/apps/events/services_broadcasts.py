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
from .models import Event
from .models_broadcasts import EventBroadcast


def locked_event(event):
    assert_write_allowed(event.makerspace_id)
    assert_mapped_write_allowed(event.makerspace_id)
    event = Event.objects.select_for_update().get(pk=event.pk)
    event.makerspace = require_module_locked(event.makerspace_id, "events")
    return event


@transaction.atomic
def compose(event, actor, **values):
    event = locked_event(event)
    campaign = EventBroadcast(event=event, makerspace=event.makerspace, created_by=actor, **values)
    authorize(campaign, actor)
    # Unsaved mapped attributes are still plaintext and strict reads reject them.
    validate_strings(values.get("subject", ""), values.get("body", ""), PLACEHOLDERS)
    from .models import EventRegistration
    if (not isinstance(campaign.statuses, list) or not campaign.statuses
            or set(campaign.statuses) - set(EventRegistration.Status.values)
            or campaign.attendance not in {"any", "attended", "not_attended"}):
        raise ValidationError("Choose valid registration and attendance filters.")
    campaign.save()
    record(actor, "event.broadcast.created", makerspace=event.makerspace, target=campaign)
    return campaign


@transaction.atomic
def change(campaign, actor, action):
    event = locked_event(campaign.event)
    campaign = EventBroadcast.objects.select_for_update().get(pk=campaign.pk, event=event)
    authorize(campaign, actor)
    if action == "queue":
        if campaign.status != "draft":
            raise ValidationError("Only drafts can be queued.")
        if EventBroadcast.objects.filter(makerspace=event.makerspace,
                queued_at__gte=timezone.now() - timedelta(hours=1)).count() >= 10:
            raise Throttled(detail="Limit of 10 broadcasts per hour for this makerspace.")
        campaign.status, campaign.queued_at = "queued", timezone.now()
    elif action == "cancel" and campaign.status in {"draft", "queued", "sending"}:
        campaign.status, campaign.completed_at = "cancelled", timezone.now()
    else:
        raise ValidationError("This campaign cannot be changed in its current state.")
    campaign.save(update_fields=["status", "queued_at", "completed_at", "updated_at"])
    record(actor, f"event.broadcast.{campaign.status}", makerspace=event.makerspace, target=campaign)
    if action == "queue":
        transaction.on_commit(lambda: enqueue("event_broadcast", campaign.pk))
    return campaign
