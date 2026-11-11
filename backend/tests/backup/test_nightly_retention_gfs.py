"""BK-09: nightly archives keep 7 daily + 4 weekly; on-demand archives keep retention_days.
BK-17: the custody endpoint tells a Space Manager when their space was last backed up."""

from datetime import datetime, timedelta, timezone as dt_timezone
import uuid

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.backup.models import BackupArchive, BackupRun, BackupRunCoverage, PlatformBackupSettings
from apps.backup.retention import DAILY_KEEP_DAYS, WEEKLY_KEEP_WEEKS, archive_expires_at
from apps.makerspaces.models import Makerspace
from tests.account_split.sweep_helpers import configured_membership, make_role_account, role_slug

pytestmark = pytest.mark.django_db
WEDNESDAY = datetime(2026, 10, 21, 2, 0, tzinfo=dt_timezone.utc)


def _client(actor):
    client = APIClient()
    client.force_authenticate(actor)
    return client


def _run():
    return BackupRun.objects.create(cohort_at=WEDNESDAY, flag_snapshot={}, status=BackupRun.Status.COMPLETE)


def _archive(*, run=None, completed_at=None, status=BackupArchive.Status.RUNNING, **fields):
    archive_id = uuid.uuid4()
    return BackupArchive.objects.create(
        id=archive_id, scope=fields.pop("scope", BackupArchive.Scope.DEPLOYMENT), backup_run=run,
        status=status, completed_at=completed_at, object_key=f"backup-archives/x/{archive_id}.tar.age",
        expires_at=None if status == BackupArchive.Status.RUNNING else completed_at + timedelta(days=7),
        **fields,
    )


def test_on_demand_archives_keep_the_configured_days():
    archive = _archive()
    assert archive_expires_at(archive, WEDNESDAY, 30) == WEDNESDAY + timedelta(days=30)


def test_first_nightly_archive_of_the_week_is_the_weekly_copy():
    archive = _archive(run=_run())
    assert archive_expires_at(archive, WEDNESDAY, 30) == WEDNESDAY + timedelta(weeks=WEEKLY_KEEP_WEEKS)


def test_later_nightly_archives_that_week_are_daily_copies():
    monday = WEDNESDAY - timedelta(days=2)
    _archive(run=_run(), completed_at=monday, status=BackupArchive.Status.AVAILABLE)
    archive = _archive(run=_run())
    assert archive_expires_at(archive, WEDNESDAY, 30) == WEDNESDAY + timedelta(days=DAILY_KEEP_DAYS)


def test_last_weeks_archive_does_not_make_this_week_daily():
    last_sunday = WEDNESDAY - timedelta(days=3)
    _archive(run=_run(), completed_at=last_sunday, status=BackupArchive.Status.AVAILABLE)
    archive = _archive(run=_run())
    assert archive_expires_at(archive, WEDNESDAY, 30) == WEDNESDAY + timedelta(weeks=WEEKLY_KEEP_WEEKS)


def test_weekly_copies_are_tracked_per_makerspace():
    one = Makerspace.objects.create(name="One", slug="gfs-one")
    two = Makerspace.objects.create(name="Two", slug="gfs-two")
    tenant = BackupArchive.Scope.MAKERSPACE
    _archive(run=_run(), completed_at=WEDNESDAY - timedelta(hours=1), status=BackupArchive.Status.AVAILABLE,
             scope=tenant, makerspace=one)
    archive = _archive(run=_run(), scope=tenant, makerspace=two)
    assert archive_expires_at(archive, WEDNESDAY, 30) == WEDNESDAY + timedelta(weeks=WEEKLY_KEEP_WEEKS)


def test_backup_status_reports_last_backup_and_nightly_switch_to_the_space_manager():
    space = Makerspace.objects.create(name="Tile", slug="custody-tile")
    actor = make_role_account(space, role_slug=role_slug("space_manager"), username="custody-tile-manager")
    configured_membership(user=actor, makerspace=space)
    client = _client(actor)
    path = reverse("admin-makerspace-backup-status", args=[space.pk])

    empty = client.get(path).data
    assert empty["last_backed_up_at"] is None and empty["nightly_backups_enabled"] is False

    run = _run()
    deployment = _archive(run=run, completed_at=WEDNESDAY, status=BackupArchive.Status.AVAILABLE)
    BackupRunCoverage.objects.create(
        run=run, makerspace=space, archive=deployment, path=BackupRunCoverage.Path.GLOBAL,
        state=BackupRunCoverage.State.COVERED, makerspace_id_snapshot=space.pk,
        completed_at_snapshot=WEDNESDAY,
    )
    settings_row = PlatformBackupSettings.load()
    settings_row.automatic_backups_enabled = True
    settings_row.save(update_fields=("automatic_backups_enabled", "updated_at"))

    data = client.get(path).data
    assert data["nightly_backups_enabled"] is True
    assert data["last_backed_up_at"] is not None
