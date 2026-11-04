"""Platform-only orchestration across every makerspace."""

from collections import Counter

from django.utils import timezone

from apps.integrations.models import EmailLog, NotificationDeliveryLog, NotificationDelivery
from apps.integrations.models_tracking import PushDeliveryAttempt
from apps.makerspaces import limits
from apps.makerspaces.models import Makerspace
from apps.makerspaces.servability import servable_queryset
from apps.makerspaces.usage_snapshot import usage_snapshot
from apps.operations.platform_signals import (
    backup_snapshot, offsite_snapshot, scheduler_snapshot,
)
from apps.operations.platform_integration_health import integration_snapshot


def platform_spaces():
    return Makerspace.objects.all()


def build_platform_dashboard():
    now = timezone.now()
    spaces = platform_spaces()
    states = Counter({state: 0 for state in Makerspace.LifecycleState.values})
    states["archived"] = 0
    for row in spaces.values("lifecycle_state", "archived_at"):
        states["archived" if row["archived_at"] else row["lifecycle_state"]] += 1
    live = list(servable_queryset(spaces).order_by("id"))
    ids = [space.pk for space in live]
    totals = Counter()
    tenants = []
    for space in live:
        usage = usage_snapshot(space)
        totals.update({row["key"]: row["used"] for row in usage["resources"]
                       if row["used"] is not None})
        tenants.append({"id": space.pk, "name": space.name, "slug": space.slug,
                        "usage": usage})
    # Scoping is resolved once at the tenant boundary; all related summaries use
    # exactly those IDs. No raw errors or recipient/subject text enters the API.
    from .deployment_projection import deployment_projection
    return {
        "deployment": deployment_projection(),
        "checked_at": now, "tenants_by_state": dict(states),
        "usage_totals": dict(totals), "tenants": tenants,
        "backup": backup_snapshot(), "offsite": offsite_snapshot(ids),
        "scheduler": scheduler_snapshot(now),
        "failed_deliveries": {
            "email": EmailLog.objects.filter(makerspace_id__in=ids, status="failed").count(),
            "notifications": _notification_failures(ids),
        },
    }


def _notification_failures(space_ids):
    logs = NotificationDeliveryLog.objects.filter(makerspace_id__in=space_ids, status="failed")
    # Staff push has per-device outcomes. A failed parent contributes only when
    # delivery failed before any device rows existed, never alongside its children.
    return (
        logs.exclude(channel="native_push").count()
        + logs.filter(channel="native_push", pushdeliveryattempt__isnull=True).count()
        + PushDeliveryAttempt.objects.filter(
            delivery_log__makerspace_id__in=space_ids, status="failed",
        ).count()
        + NotificationDelivery.objects.filter(
            makerspace_id__in=space_ids, state="failed",
        ).exclude(channel="email").count()
    )


def tenant_check_context(space, key):
    data = {"space": space}
    if key == "storage":
        data["usage"] = {"resources": [{"key": "storage", "used": space.storage_bytes_used,
                                         "limit": limits.resource_limit(space, "storage")}]}
    if key in {"email", "telegram"}:
        data["health"] = integration_snapshot(space)
    return data
