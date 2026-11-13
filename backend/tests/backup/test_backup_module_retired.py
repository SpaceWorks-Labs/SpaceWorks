"""P1b (#111 Q2): the `backup` module key is retired; managers keep a read-only status line."""
from tests.account_split.sweep_helpers import (
    configured_membership as _configured_membership,
    make_role_account as _make_role_account,
    role_slug as _role_slug,
)

import importlib
import uuid
from datetime import timedelta

import pytest
from django.apps import apps as django_apps
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.backup.models import BackupArchive, PlatformBackupSettings
from apps.makerspaces.models import Makerspace
from apps.makerspaces.module_registry import MODULE_KEYS

pytestmark = pytest.mark.django_db


def _client(actor):
    client = APIClient()
    client.force_authenticate(actor)
    return client


def _manager(space, username):
    actor = _make_role_account(space, role_slug=_role_slug("space_manager"), username=username)
    _configured_membership(user=actor, makerspace=space)
    return actor


def _archive(space, **fields):
    return BackupArchive.objects.create(
        makerspace=space, scope="makerspace", object_key=f"backup/{uuid.uuid4()}",
        status="available", completed_at=timezone.now(),
        expires_at=timezone.now() + timedelta(days=1), **fields,
    )


def test_the_backup_key_is_gone_from_the_registry():
    assert "backup" not in MODULE_KEYS


def test_recipient_and_custody_routes_no_longer_exist():
    for name, args in (
        ("admin-archive-recipient-list-create", [1]),
        ("admin-archive-recipient-compromise", [1, 1]),
        ("admin-makerspace-backup-custody", [1]),
    ):
        with pytest.raises(NoReverseMatch):
            reverse(name, args=args)


def test_manager_reads_the_last_backup_line_for_their_space_only():
    space = Makerspace.objects.create(name="Own", slug="status-own")
    foreign = Makerspace.objects.create(name="Foreign", slug="status-foreign")
    archive = _archive(space)
    PlatformBackupSettings.objects.update_or_create(pk=1, defaults={"automatic_backups_enabled": True})
    client = _client(_manager(space, "status-manager"))
    response = client.get(reverse("admin-makerspace-backup-status", args=[space.pk]))
    assert response.status_code == 200, response.data
    assert response.data["last_backed_up_at"] is not None
    assert response.data["last_backed_up_at"][:19] == archive.completed_at.isoformat()[:19]
    assert response.data["nightly_backups_enabled"] is True
    assert client.get(reverse("admin-makerspace-backup-status", args=[foreign.pk])).status_code == 403


def test_status_line_needs_no_module_and_reports_no_backup_yet():
    space = Makerspace.objects.create(name="Empty", slug="status-empty", enabled_modules=[])
    response = _client(_manager(space, "status-empty-manager")).get(
        reverse("admin-makerspace-backup-status", args=[space.pk])
    )
    assert response.status_code == 200, response.data
    assert response.data["last_backed_up_at"] is None


def test_managers_cannot_request_list_or_download_archives(monkeypatch):
    monkeypatch.setattr("apps.backup.views_archives.run_backup_archive_task.delay", lambda _id: None)
    space = Makerspace.objects.create(name="Manager", slug="no-manager-archives")
    archive = _archive(space)
    client = _client(_manager(space, "archive-manager"))
    url = reverse("admin-makerspace-backups", args=[space.pk])
    assert client.get(url).status_code == 403
    assert client.post(url, {}, format="json").status_code == 403
    assert client.post(reverse("admin-backup-download-url", args=[archive.pk])).status_code == 403
    assert not BackupArchive.objects.filter(makerspace=space).exclude(pk=archive.pk).exists()


def test_the_superadmin_still_lists_makerspace_archives():
    space = Makerspace.objects.create(name="Super", slug="super-archives")
    archive = _archive(space)
    actor = User.objects.create_superuser(username="archives-super", password="x")
    response = _client(actor).get(reverse("admin-makerspace-backups", args=[space.pk]))
    assert response.status_code == 200
    assert [row["id"] for row in response.data] == [str(archive.pk)]


def test_retirement_migration_strips_the_key_from_every_row():
    space = Makerspace.objects.create(name="Legacy", slug="legacy-backup-key")
    Makerspace.objects.filter(pk=space.pk).update(enabled_modules=["inventory_core", "backup", "email"])
    migration = importlib.import_module("apps.backup.migrations.0033_retire_backup_module")
    migration.strip_backup_module(django_apps, None)
    space.refresh_from_db()
    assert space.enabled_modules == ["inventory_core", "email"]
