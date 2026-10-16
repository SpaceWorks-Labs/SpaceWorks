"""Audited draft/queue/cancel services; tenant lock serializes the hourly quota."""

from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import Throttled, ValidationError

from apps.audit.services import record
from apps.encryption.write_fence import assert_mapped_write_allowed
from apps.integrations.broadcasts_templates import validate_strings
from apps.integrations.broadcasts_worker import enqueue
from apps.makerspaces.guards import require_module_locked
from apps.tenant_migration.gate_runtime import assert_write_allowed
from .broadcasts import PLACEHOLDERS, authorize
from .models import BookableSpace
from .models_broadcasts import BookingBroadcast


def locked_space(space):
    assert_write_allowed(space.makerspace_id)
    assert_mapped_write_allowed(space.makerspace_id)
    # Ordinary booking workflows lock resource -> tenant; the shared worker
    # locks tenant -> campaign and never takes a resource lock.
    space = BookableSpace.objects.select_for_update().get(pk=space.pk)
    makerspace = require_module_locked(space.makerspace_id, "bookings")
    space.makerspace = makerspace
    return space


@transaction.atomic
def compose(space, actor, *, subject, body, window_start, window_end, statuses=None):
    space = locked_space(space)
    statuses = ["confirmed"] if statuses is None else statuses
    now = timezone.now()
    if (not isinstance(window_start, datetime) or not isinstance(window_end, datetime)
            or timezone.is_naive(window_start) or timezone.is_naive(window_end)
            or window_start < now - timedelta(minutes=1) or window_end <= now or window_end <= window_start
            or window_end > now + timedelta(days=366)):
        raise ValidationError("Choose a future window ending within 366 days.")
    if (not isinstance(statuses, list) or not statuses
            or any(not isinstance(status, str) or status not in {"pending", "confirmed"} for status in statuses)):
        raise ValidationError({"statuses": "Choose pending and/or confirmed reservations."})
    validate_strings(subject, body, PLACEHOLDERS)
    campaign = BookingBroadcast(space=space, makerspace=space.makerspace, created_by=actor,
        subject=subject, body=body, window_start=window_start, window_end=window_end, statuses=sorted(set(statuses)))
    authorize(campaign, actor)
    campaign.save()
    record(actor, "booking.broadcast.created", makerspace=space.makerspace, target=campaign)
    return campaign


@transaction.atomic
def change(campaign, actor, action):
    space = locked_space(campaign.space)
    campaign = BookingBroadcast.objects.select_for_update().get(pk=campaign.pk, space=space)
    authorize(campaign, actor)
    now = timezone.now()
    if action == "queue":
        if campaign.status != "draft" or campaign.window_end <= now:
            raise ValidationError("Only drafts with a future window can be queued.")
        if BookingBroadcast.objects.filter(makerspace=space.makerspace,
                queued_at__gte=now - timedelta(hours=1)).count() >= 10:
            raise Throttled(detail="Limit of 10 broadcasts per hour for this makerspace.")
        campaign.status, campaign.queued_at = "queued", now
    elif action == "cancel" and campaign.status in {"draft", "queued", "sending"}:
        campaign.status, campaign.completed_at = "cancelled", now
    else:
        raise ValidationError("This campaign cannot be changed in its current state.")
    campaign.save(update_fields=["status", "queued_at", "completed_at", "updated_at"])
    record(actor, f"booking.broadcast.{campaign.status}", makerspace=space.makerspace, target=campaign)
    if action == "queue":
        transaction.on_commit(lambda: enqueue("booking_broadcast", campaign.pk))
    return campaign
