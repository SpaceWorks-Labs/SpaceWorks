"""Copied backup-archive download bearers must not survive a database restore."""

import json
import uuid
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.backup.models import BackupArchive, DeploymentRecoveryState, RestoreOperation
from apps.backup.raw_projection import raw_records
from apps.backup.restore_control_records import rehydrate_control_record
from apps.backup.services_access import (
    invalidate_download_tokens_after_restore,
    issue_download_token,
)
from tests.backup.test_archive_expiry import _mid_build_archive

pytestmark = pytest.mark.django_db

BEARER = ("download_token_digest", "download_token_expires_at", "download_token_consumed_at")
CLEARED_BEARER = {
    "download_token_digest": "",
    "download_token_expires_at": None,
    "download_token_consumed_at": None,
}


class _Body:
    def iter_chunks(self):
        yield b"age-encrypted"


@pytest.fixture
def token_archive(settings):
    settings.BACKUP_DOWNLOAD_TTL_SECONDS = 30 * 24 * 60 * 60
    admin = User.objects.create_superuser(username="restore-archive-super", password="secret")
    archive = BackupArchive.objects.create(
        scope=BackupArchive.Scope.DEPLOYMENT,
        requested_by=admin,
        status=BackupArchive.Status.AVAILABLE,
        object_key=f"backup-archives/deployment/{uuid.uuid4()}.tar.age",
        age_encrypted=True,
        expires_at=timezone.now() + timedelta(days=60),
    )
    token, _ = issue_download_token(archive, admin)
    return archive, admin, token


def _path(archive, token):
    return reverse(
        "backup-archive-download", kwargs={"archive_id": archive.pk, "token": token}
    )


def _bearer(archive):
    return BackupArchive.objects.values(*BEARER).get(pk=archive.pk)


def _rehydrate(kind, tmp_path):
    restored = _mid_build_archive()
    control = tmp_path / "control.json"
    manifest = tmp_path / "manifest.json"
    control.write_text(json.dumps({"decision": "proceed"}), encoding="utf-8")
    manifest.write_text(json.dumps({"archive_id": str(restored.pk)}), encoding="utf-8")
    rehydrate_control_record(uuid.uuid4(), {
        "archive_id": str(restored.pk),
        "kind": kind,
        "control_record": str(control),
        "manifest": str(manifest),
    })
    state = DeploymentRecoveryState.load()
    state.mode = DeploymentRecoveryState.Mode.NORMAL
    state.save(update_fields=("mode", "updated_at"))
    return restored


@pytest.mark.parametrize("kind", list(RestoreOperation.Kind))
def test_classic_restore_rejects_replayed_archive_token_but_allows_new_token(
    kind, token_archive, monkeypatch, tmp_path
):
    archive, admin, token = token_archive
    captured = _bearer(archive)
    assert captured["download_token_digest"]
    assert captured["download_token_consumed_at"] is None
    assert captured["download_token_expires_at"] > timezone.now() + timedelta(days=1)
    monkeypatch.setattr("apps.backup.views_archives.storage.open_archive", lambda _key: _Body())
    anonymous = APIClient()
    downloaded = anonymous.get(_path(archive, token))
    assert downloaded.status_code == 200
    assert b"".join(downloaded.streaming_content) == b"age-encrypted"
    assert _bearer(archive)["download_token_consumed_at"] is not None

    # pg_restore resurrects the captured, unused bearer after its live consumption.
    BackupArchive.objects.filter(pk=archive.pk).update(**captured)
    restored = _rehydrate(kind, tmp_path)

    assert anonymous.get(_path(archive, token)).status_code == 404
    assert _bearer(archive) == CLEARED_BEARER
    restored.refresh_from_db()
    assert restored.status == BackupArchive.Status.AVAILABLE
    fresh_token, _ = issue_download_token(archive, admin)
    assert fresh_token != token
    downloaded = anonymous.get(_path(archive, fresh_token))
    assert downloaded.status_code == 200
    assert b"".join(downloaded.streaming_content) == b"age-encrypted"


def test_archive_sweep_routes_to_default_database(token_archive, monkeypatch):
    archive, _admin, _token = token_archive
    BackupArchive.objects.filter(pk=archive.pk).update(
        download_token_consumed_at=timezone.now()
    )
    manager = BackupArchive.objects
    using = Mock(wraps=manager.using)
    monkeypatch.setattr(manager, "using", using)

    assert invalidate_download_tokens_after_restore(using="default") == 1

    using.assert_called_once_with("default")
    assert _bearer(archive) == CLEARED_BEARER


def test_archive_sweep_leaves_archive_without_token_unchanged():
    archive = _mid_build_archive()
    queryset = BackupArchive.objects.filter(pk=archive.pk)
    before = raw_records(queryset, BackupArchive)

    assert invalidate_download_tokens_after_restore() == 0

    assert raw_records(queryset, BackupArchive) == before
