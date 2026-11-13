"""Operations block and module matrix of the platform overview (#183A).

Outbox, backups, restore drills and storage belong to a space, so they are per-space
rows. Security blocks (IP auto-blocks, unusual-login alerts) are deployment telemetry
with no tenant, so they are platform-only numbers and never split by space.
"""

from apps.makerspaces.module_registry import MODULES, module_available
from apps.makerspaces.platform import module_enabled
from apps.operations.platform_overview_blocks import Block, Metric, always_on, count_by_space, in_window
from config.locale_resolution import display


def _operations(ids, window, now):
    from apps.backup.models import BackupArchive
    from apps.backup.models_drill import RestoreDrillReport
    from apps.integrations.models_contract import NotificationDelivery
    from apps.integrations.models_email import EmailLog
    from apps.makerspaces.models import Makerspace

    email = EmailLog.objects.filter(makerspace_id__in=ids)
    archives = in_window(BackupArchive.objects.filter(scope="makerspace", makerspace_id__in=ids), "created_at", window)
    drills = in_window(RestoreDrillReport.objects.filter(makerspace_id_snapshot__in=ids), "started_at", window)
    failed_deliveries = in_window(NotificationDelivery.objects.filter(makerspace_id__in=ids, state="failed"),
                                  "failed_at", window)
    return {
        "storage_bytes": dict(Makerspace.objects.filter(pk__in=ids).values_list("pk", "storage_bytes_used")),
        "email_pending": count_by_space(email.filter(status__in=("pending", "sending"))),
        "email_failed": count_by_space(in_window(email.filter(status="failed"), "created_at", window)),
        "deliveries_failed": count_by_space(failed_deliveries),
        "backups": count_by_space(archives.filter(status="available")),
        "backup_failures": count_by_space(archives.filter(status="failed")),
        "drills_passed": count_by_space(drills.filter(outcome="passed"), "makerspace_id_snapshot"),
        "drills_failed": count_by_space(drills.filter(outcome="failed"), "makerspace_id_snapshot"),
    }


def _operations_platform(window, now):
    from apps.accounts.models_ip_access import IPAutoBlock
    from apps.accounts.models_login_risk import SecurityAlert
    from apps.backup.models import BackupArchive
    from apps.integrations.models_email import EmailLog

    platform_email = EmailLog.objects.filter(makerspace__isnull=True)
    return {
        "platform_email_pending": platform_email.filter(status__in=("pending", "sending")).count(),
        "platform_email_failed": in_window(platform_email.filter(status="failed"), "created_at", window).count(),
        "platform_backups": in_window(BackupArchive.objects.filter(scope="deployment", status="available"),
                                      "created_at", window).count(),
        "platform_backup_failures": in_window(BackupArchive.objects.filter(scope="deployment", status="failed"),
                                              "created_at", window).count(),
        "ip_blocks_active": IPAutoBlock.objects.filter(blocked_until__gt=now).count(),
        "ip_blocks": in_window(IPAutoBlock.objects.all(), "created_at", window).count(),
        "security_alerts": in_window(SecurityAlert.objects.all(), "sent_at", window).count(),
    }


OPERATIONS = Block(
    key="operations", label="Operations", switches=(), gate=always_on,
    metrics=(
        Metric("storage_bytes", "Storage used", unit="bytes", timing="snapshot"),
        Metric("email_pending", "Emails waiting to send", timing="snapshot"),
        Metric("email_failed", "Emails failed"),
        Metric("deliveries_failed", "Notifications failed"),
        Metric("backups", "Space backups made"),
        Metric("backup_failures", "Space backups failed"),
        Metric("drills_passed", "Restore drills passed"),
        Metric("drills_failed", "Restore drills failed"),
    ),
    collect=_operations,
    platform_metrics=(
        Metric("platform_email_pending", "Platform emails waiting", timing="snapshot"),
        Metric("platform_email_failed", "Platform emails failed"),
        Metric("platform_backups", "Whole-platform backups made"),
        Metric("platform_backup_failures", "Whole-platform backups failed"),
        Metric("ip_blocks_active", "Networks blocked now", timing="snapshot"),
        Metric("ip_blocks", "Network blocks started"),
        Metric("security_alerts", "Unusual sign-in alerts sent"),
    ),
    collect_platform=_operations_platform,
)


def module_matrix(spaces):
    """Which spaces have which module on; only modules this deployment ships."""
    rows = []
    for module in MODULES:
        if not module_available(module.key):
            continue
        on = [space.pk for space in spaces if module_enabled(space, module.key)]
        rows.append({"key": module.key, "label": display(module.label), "on_in": len(on),
                     "off_in": len(spaces) - len(on), "space_ids": on})
    return rows

