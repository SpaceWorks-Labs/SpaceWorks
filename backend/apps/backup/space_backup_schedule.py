"""Nightly one-space archives for every live makerspace (owner decision #111 Q4).

The same "automatic backups" switch that runs the nightly whole-platform backup turns
these on. Each beat tick builds at most ``SPACES_PER_TICK`` archives, oldest-covered
space first, so one tick stays bounded on a small server and the free profile; a space
whose last nightly archive failed is simply due again on the next tick. Archives build
one at a time under the deployment lease, exactly like a "Back up now".
"""

from datetime import timedelta

from django.db.models import F, Max, Q
from django.utils import timezone

from apps.backup.models import BackupArchive, PlatformBackupSettings
from apps.makerspaces.servability import servable_queryset

NIGHTLY_INTERVAL = timedelta(hours=20)
SPACES_PER_TICK = 2
_LIVE_STATES = (
    BackupArchive.Status.PENDING, BackupArchive.Status.RUNNING,
    BackupArchive.Status.PROMOTING, BackupArchive.Status.AVAILABLE,
)


def due_spaces(now=None, limit=SPACES_PER_TICK):
    now = now or timezone.now()
    recent = BackupArchive.objects.filter(
        scope=BackupArchive.Scope.MAKERSPACE, trigger=BackupArchive.Trigger.NIGHTLY,
        created_at__gte=now - NIGHTLY_INTERVAL, status__in=_LIVE_STATES,
    ).values("makerspace_id")
    nightly = Q(backup_archives__trigger=BackupArchive.Trigger.NIGHTLY,
                backup_archives__status=BackupArchive.Status.AVAILABLE)
    return list(
        servable_queryset().exclude(pk__in=recent)
        .annotate(last_nightly=Max("backup_archives__completed_at", filter=nightly))
        .order_by(F("last_nightly").asc(nulls_first=True), "pk")[:limit]
    )


def run_due_space_backups(limit=SPACES_PER_TICK):
    """Build the next due spaces' nightly archives; returns how many completed."""
    if not PlatformBackupSettings.objects.filter(pk=1, automatic_backups_enabled=True).exists():
        return 0
    from apps.backup.services import create_archive, run_archive

    completed = 0
    for space in due_spaces(limit=limit):
        archive = create_archive(
            None, scope=BackupArchive.Scope.MAKERSPACE, makerspace=space,
            trigger=BackupArchive.Trigger.NIGHTLY,
        )
        result = run_archive(archive.pk)
        completed += bool(result and result.status == BackupArchive.Status.AVAILABLE)
    return completed


def schedule_overview():
    """One schedule view: the whole-platform nightly backup and the per-space nightlies."""
    from django.conf import settings

    from apps.backup.retention import DAILY_KEEP_DAYS, WEEKLY_KEEP_WEEKS

    row = PlatformBackupSettings.load()
    own = Q(backup_archives__scope="makerspace", backup_archives__status="available")
    spaces = servable_queryset().annotate(
        last_nightly_at=Max("backup_archives__completed_at", filter=own & Q(backup_archives__trigger="nightly")),
        last_backup_at=Max("backup_archives__completed_at", filter=own),
    ).order_by("name")
    return {
        "automatic_backups_enabled": row.automatic_backups_enabled,
        "platform_nightly": "Every night at 02:00",
        "spaces_nightly": "Every night between 01:00 and 07:50, a few spaces at a time",
        "spaces_per_tick": SPACES_PER_TICK,
        "daily_keep_days": DAILY_KEEP_DAYS,
        "weekly_keep_weeks": WEEKLY_KEEP_WEEKS,
        "on_demand_keep_days": row.retention_days,
        "server_restore_key_configured": bool(settings.TENANT_MIGRATION_AGE_RECIPIENT
                                              and settings.TENANT_MIGRATION_AGE_IDENTITY_FILE),
        "last_platform_success_at": row.last_success_at,
        "spaces": [{"makerspace_id": space.pk, "slug": space.slug, "name": space.name,
                    "last_nightly_at": space.last_nightly_at, "last_backup_at": space.last_backup_at}
                   for space in spaces],
    }
