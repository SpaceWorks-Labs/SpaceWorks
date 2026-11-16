"""Bounded legacy room rows use the original claim, source and provider boundary."""
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone


def drain_channels(context, cursor):
    from apps.integrations.models import NotificationDeliveryLog as Log
    from apps.integrations.tasks import _claim_notification_log
    from apps.integrations.dispatch_channels import _deliver_notification
    from apps.tenant_migration.gate_runtime import fanout_tenant_write
    now = timezone.now()
    due = Log.objects.filter(attempts__lt=4).filter(
        Q(status="pending") | Q(status="failed", error__startswith="notification_delivery_failed",
            updated_at__lte=now - timedelta(seconds=60)))
    seeds = list(due.filter(pk__gt=cursor).order_by("pk").values_list("pk", "makerspace_id")[:2])
    processed = 0
    for pk, makerspace_id in seeds[:1]:  # one row per chunk
        context.check()
        with fanout_tenant_write(makerspace_id, operation="free_channel_drain", counts={}) as allowed:
            if not allowed:
                continue
            context.check()
            log = _claim_notification_log(pk)
            if log is not None:
                context.check()
                _deliver_notification(log)
                processed = 1
    if seeds:
        context.check()
    return {"processed": processed, "remaining": len(seeds) > 1, "cursor": seeds[0][0] if len(seeds) > 1 else 0}
