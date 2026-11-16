"""Nightly per-space archives (#111 Q4), dual recipients (Q3) and their retention."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.backup import age_recipients
from apps.backup.models import BackupArchive, PlatformBackupSettings
from apps.backup.retention import DAILY_KEEP_DAYS, WEEKLY_KEEP_WEEKS, archive_expires_at
from apps.backup.space_backup_schedule import due_spaces, run_due_space_backups
from apps.makerspaces.models import Makerspace

pytestmark = pytest.mark.django_db


def _space(slug):
    return Makerspace.objects.create(name=slug.title(), slug=slug)


def _archive(space, *, trigger="nightly", status="available", age=timedelta(hours=1)):
    created = timezone.now() - age
    row = BackupArchive.objects.create(
        scope="makerspace", makerspace=space, trigger=trigger, status=status,
        object_key=f"backup-archives/makerspace/{space.slug}-{created.timestamp()}.tar.age",
        completed_at=created if status == "available" else None,
        expires_at=created + timedelta(days=7) if status == "available" else None,
    )
    BackupArchive.objects.filter(pk=row.pk).update(created_at=created)
    return row


def test_switch_off_builds_nothing(monkeypatch):
    _space("nightly-off")
    PlatformBackupSettings.objects.update_or_create(pk=1, defaults={"automatic_backups_enabled": False})
    monkeypatch.setattr("apps.backup.services.run_archive", lambda _pk: pytest.fail("must not run"))
    assert run_due_space_backups() == 0
    assert not BackupArchive.objects.exists()


def test_switch_on_builds_the_oldest_due_spaces_first_bounded_per_tick(monkeypatch):
    never = _space("nightly-never")
    stale = _space("nightly-stale")
    fresh = _space("nightly-fresh")
    _archive(stale, age=timedelta(hours=30))
    _archive(fresh, age=timedelta(hours=2))
    assert [space.pk for space in due_spaces(limit=5)] == [never.pk, stale.pk]
    PlatformBackupSettings.objects.update_or_create(pk=1, defaults={"automatic_backups_enabled": True})
    ran = []

    def fake_run(archive_id):
        ran.append(archive_id)
        BackupArchive.objects.filter(pk=archive_id).update(status="available", completed_at=timezone.now(),
                                                           expires_at=timezone.now() + timedelta(days=7))
        return BackupArchive.objects.get(pk=archive_id)
    monkeypatch.setattr("apps.backup.services.run_archive", fake_run)
    assert run_due_space_backups(limit=1) == 1
    first = BackupArchive.objects.get(pk=ran[0])
    assert first.makerspace == never and first.trigger == "nightly" and first.format == "tenant_slice_v2"
    assert [space.pk for space in due_spaces(limit=5)] == [stale.pk]


def test_a_failed_nightly_is_due_again():
    space = _space("nightly-failed")
    _archive(space, status="failed", age=timedelta(minutes=5))
    assert [row.pk for row in due_spaces()] == [space.pk]


def test_one_space_archives_go_to_the_platform_and_server_keys(settings):
    settings.BACKUP_AGE_RECIPIENT = "age1platform"
    settings.TENANT_MIGRATION_AGE_RECIPIENT = "age1server"
    space = BackupArchive(scope="makerspace")
    deployment = BackupArchive(scope="deployment")
    assert [item["public_recipient"] for item in age_recipients.selection_for(space)] == ["age1platform", "age1server"]
    assert [item["public_recipient"] for item in age_recipients.selection_for(deployment)] == ["age1platform"]
    settings.TENANT_MIGRATION_AGE_RECIPIENT = ""
    assert [item["public_recipient"] for item in age_recipients.selection_for(space)] == ["age1platform"]


def test_nightly_space_archives_rotate_like_the_nightly_run():
    space = _space("nightly-retention")
    now = timezone.now()
    first = _archive(space, age=timedelta(days=1))
    assert archive_expires_at(first, now, 30) in (now + timedelta(days=DAILY_KEEP_DAYS),
                                                   now + timedelta(weeks=WEEKLY_KEEP_WEEKS))
    on_demand = BackupArchive(scope="makerspace", makerspace=space, trigger="on_demand")
    assert archive_expires_at(on_demand, now, 30) == now + timedelta(days=30)
