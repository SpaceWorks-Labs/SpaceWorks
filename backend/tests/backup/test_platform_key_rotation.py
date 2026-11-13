"""Platform key rotation (BK-68): retire, list, re-encrypt or purge, never reuse (release 2 L11)."""
import subprocess

import pytest

from apps.audit.models import AuditLog
from apps.backup import storage
from apps.backup.archive_reencrypt import can_reencrypt, purge_archive, reencrypt_archive, run_requested_reencryption
from apps.backup.models import BackupArchive, PlatformBackupSettings
from apps.backup.platform_key_rotation import KeyRotationError, record_rotation, stale_archives
from apps.backup.services import create_archive, run_archive
from tests.backup.test_space_restore_flow import _backup, _keypair, _superadmin, restore_keys  # noqa: F401
from tests.backup.space_restore_helpers import seed_space, make_user

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def _encryption():
    from tests.encryption.conftest import enabled_encryption
    with enabled_encryption():
        yield


def _opens_with(identity, archive, tmp_path):
    path = tmp_path / f"{archive.pk}.age"
    with path.open("wb") as handle:
        for chunk in storage.open_archive(archive.object_key).iter_chunks():
            handle.write(chunk)
    return subprocess.run(["age", "--decrypt", "-i", str(identity), "-o", "/dev/null", str(path)],
                          capture_output=True).returncode == 0


def test_rotation_retires_the_old_key_reencrypts_and_refuses_reuse(restore_keys, tmp_path):
    root = _superadmin()
    space, _request = seed_space("rotate-space", make_user("rotate-member"))
    archive = _backup(space, root)
    old_platform = restore_keys.BACKUP_AGE_RECIPIENT
    with pytest.raises(KeyRotationError) as unchanged:
        record_rotation(root, "platform")
    assert unchanged.value.code == "key_unchanged"
    new_identity, new_platform = _keypair(tmp_path, "platform-2")
    restore_keys.BACKUP_AGE_RECIPIENT = new_platform
    result = record_rotation(root, "platform")
    assert result["stale_archives"] == 1 and len(result["retired"]) == 1
    assert [row.pk for row in stale_archives()] == [archive.pk] and can_reencrypt(archive)
    old_key = archive.object_key
    updated = reencrypt_archive(archive, actor=root)
    assert updated.object_key != old_key and stale_archives() == []
    assert _opens_with(new_identity, updated, tmp_path)
    assert [item["public_recipient"] for item in updated.manifest["recipients"]][0] == new_platform
    assert updated.expires_at == archive.expires_at and updated.completed_at == archive.completed_at
    assert {"backup.platform_key_rotated", "backup.reencrypted"} <= set(
        AuditLog.objects.values_list("action", flat=True))
    restore_keys.BACKUP_AGE_RECIPIENT = old_platform
    with pytest.raises(KeyRotationError) as reused:
        record_rotation(root, "platform")
    assert reused.value.code == "key_reused"
    refused = run_archive(create_archive(root, scope="makerspace", makerspace=space).pk)
    assert refused.status == BackupArchive.Status.FAILED


def test_a_requested_background_reencryption_runs_in_batches_and_clears_itself(restore_keys, tmp_path):
    root = _superadmin()
    space, _request = seed_space("rotate-batch", make_user("rotate-batch-member"))
    _backup(space, root)
    _backup(space, root)
    _identity, new_platform = _keypair(tmp_path, "platform-3")
    restore_keys.BACKUP_AGE_RECIPIENT = new_platform
    record_rotation(root, "platform")
    assert run_requested_reencryption() == 0  # nothing requested
    PlatformBackupSettings.objects.filter(pk=PlatformBackupSettings.load().pk).update(reencrypt_requested_at="2026-11-01T00:00Z")
    assert run_requested_reencryption(limit=1) == 1
    assert PlatformBackupSettings.load().reencrypt_requested_at is not None
    assert run_requested_reencryption(limit=5) == 1
    assert PlatformBackupSettings.load().reencrypt_requested_at is None and stale_archives() == []


def test_purge_deletes_the_bytes_and_a_non_superadmin_cannot_rotate(restore_keys, tmp_path):
    from django.core.exceptions import ValidationError
    root = _superadmin()
    space, _request = seed_space("rotate-purge", make_user("rotate-purge-member"))
    archive = _backup(space, root)
    _identity, new_platform = _keypair(tmp_path, "platform-4")
    restore_keys.BACKUP_AGE_RECIPIENT = new_platform
    with pytest.raises(ValidationError):
        record_rotation(make_user("rotate-not-root"), "platform")
    record_rotation(root, "platform")
    purge_archive(archive, actor=root)
    assert not BackupArchive.objects.filter(pk=archive.pk).exists()
    with pytest.raises(storage.BackupStorageError):
        storage.open_archive(archive.object_key).read()
    assert AuditLog.objects.filter(action="backup.purged").count() == 1
