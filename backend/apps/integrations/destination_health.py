"""Auto-disable dead chat rooms (X38, NM-92) with a staff notice.

A room (NotificationDestination) whose last five deliveries since it was last edited all
FAILED is switched off: posting to a deleted Slack webhook or a Telegram chat the bot
was removed from only burns quota and hides the problem. The room keeps all settings
and history; a staff member fixes it and switches it back on, which restarts the count
(only deliveries after the room's last edit are considered). Every switch-off is audited
and announced in the staff notices with the room's label and channel, never a credential.
Runs hourly with a bounded batch.
"""

import logging

from celery import shared_task

from apps.audit.services import record
from apps.operations.cloud_jobs import bounded

logger = logging.getLogger(__name__)
WINDOW = 5


def dead(destination):
    from .models_notifications import NotificationDeliveryLog
    statuses = list(NotificationDeliveryLog.objects.filter(
        destination=destination, created_at__gt=destination.updated_at,
    ).exclude(status__in=("pending", "sending", "skipped")).order_by("-created_at", "-pk")
        .values_list("status", flat=True)[:WINDOW])
    return len(statuses) == WINDOW and all(status == "failed" for status in statuses)


def disable(destination):
    from django.db import transaction
    from apps.notifications.emit import emit_notification
    from apps.tenant_migration.gate_runtime import tenant_write
    from .models_destinations import NotificationDestination
    with tenant_write(destination.makerspace_id), transaction.atomic():
        row = NotificationDestination.objects.select_for_update().get(pk=destination.pk)
        if not row.is_active or not dead(row):
            return False
        row.is_active = False
        row.save(update_fields=["is_active", "updated_at"])
        record(None, "notification.destination_auto_disabled", makerspace=row.makerspace, target=row,
               meta={"channel": row.channel, "failures": WINDOW})
        emit_notification(row.makerspace, level="warning", event="destination_auto_disabled",
                          title=f"Chat room switched off: {row.label}",
                          body=(f"Space Works stopped posting to {row.label} ({row.get_channel_display()}) after "
                                f"{WINDOW} failed deliveries in a row. Check the room's settings, then switch it "
                                "back on."),
                          url_path="settings/notifications")
    return True


@shared_task
def disable_dead_destinations_task():
    from apps.makerspaces.servability import servable_queryset
    from .models_destinations import NotificationDestination
    counts = {"disabled": 0, "failed": 0}
    from .dispatch_channels import channel_module_blocks
    rows = (NotificationDestination.objects.filter(is_active=True, makerspace__in=servable_queryset().values("pk"))
            .select_related("makerspace").order_by("pk"))
    for destination in bounded.page(rows, "notification-destination-health"):
        # A room whose channel module is off is left alone (#183B); it is kept as is.
        if channel_module_blocks(destination.makerspace, destination.channel):
            continue
        try:
            if dead(destination) and disable(destination):
                counts["disabled"] += 1
        except Exception:
            counts["failed"] += 1
            logger.warning("destination_health_failed", extra={"destination_id": destination.pk})
    return counts
