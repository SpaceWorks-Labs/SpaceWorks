"""When a completed backup archive expires (BK-09: nightly backups keep 7 daily + 4 weekly).

Archives from the nightly scheduled run, and the nightly per-space archives (#111 Q4),
are rotated grandfather-father-son style:
every one is kept for `DAILY_KEEP_DAYS`, and the first one completed in each ISO week
(per scope and makerspace) is the weekly copy, kept for `WEEKLY_KEEP_WEEKS` weeks.
On-demand archives, which an operator asked for explicitly, keep the configurable
flat `PlatformBackupSettings.retention_days`.

Expiry is stamped once, at completion, so the existing `purge_expired_archives`
sweep stays the only thing that deletes archive bytes.
"""

from datetime import timedelta

from django.db import models

DAILY_KEEP_DAYS = 7
WEEKLY_KEEP_WEEKS = 4


def _week_start(moment):
    start = moment - timedelta(days=moment.isocalendar().weekday - 1)
    return start.replace(hour=0, minute=0, second=0, microsecond=0)


def is_weekly_copy(archive, completed_at):
    """The first nightly archive of this scope/makerspace to complete in its ISO week."""
    from apps.backup.models import BackupArchive

    return not (
        BackupArchive.objects.filter(
            scope=archive.scope,
            makerspace_id=archive.makerspace_id,
            completed_at__gte=_week_start(completed_at),
            completed_at__lt=completed_at,
            status__in=(BackupArchive.Status.AVAILABLE, BackupArchive.Status.EXPIRED),
        )
        .filter(models.Q(backup_run__isnull=False) | models.Q(trigger="nightly"))
        .exclude(pk=archive.pk)
        .exists()
    )


def _is_nightly(archive):
    return archive.backup_run_id is not None or archive.trigger == "nightly"


def archive_expires_at(archive, completed_at, retention_days):
    if not _is_nightly(archive):
        return completed_at + timedelta(days=retention_days)
    if is_weekly_copy(archive, completed_at):
        return completed_at + timedelta(weeks=WEEKLY_KEEP_WEEKS)
    return completed_at + timedelta(days=DAILY_KEEP_DAYS)
