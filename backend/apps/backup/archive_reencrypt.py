"""Re-encrypt or purge archives still encrypted to a rotated-out key (release 2 L11, BK-68).

Only a ONE-SPACE archive can be re-encrypted on the server: it is also encrypted to this
server's restore key, so the server opens it (with the current restore identity, or the
previous one the operator hands the host command with ``--old-identity-file`` for that
run only) and re-encrypts it to today's platform and restore keys. A whole-platform
archive is encrypted to the platform key alone, whose private half never lives on the
server (#144b): it can only be kept until it expires or purged here.

Re-encryption is idempotent (a re-encrypted archive is no longer stale) and never
changes an archive's identity, expiry or restore point: only its bytes, digest, size and
recorded recipients. The new bytes are uploaded to a new key and streamed back for size
and SHA-256 before the row switches; the old object is deleted after commit.
"""
import hashlib
import subprocess
import tempfile
import uuid
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.audit import services as audit

from . import storage
from .age_recipients import selection_for
from .artifact_ledger import mark_managed_bytes_deleted
from .models import BackupArchive, BackupArtifactLedger
from .platform_key_rotation import KeyRotationError, archive_fingerprints, fingerprint_of, stale_archives

BATCH = 5


def _identity_recipient(identity_file):
    result = subprocess.run(["age-keygen", "-y", str(identity_file)], check=True, capture_output=True, text=True)
    return result.stdout.strip()


def can_reencrypt(row, identity_file=None):
    if row.scope != BackupArchive.Scope.MAKERSPACE or not (row.manifest or {}).get("server_restorable"):
        return False
    identity = identity_file or settings.TENANT_MIGRATION_AGE_IDENTITY_FILE
    if not identity:
        return False
    try:
        recipient = _identity_recipient(identity)
    except (OSError, subprocess.SubprocessError):
        return False
    return fingerprint_of(recipient) in archive_fingerprints(row)["server"]


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(key, destination):
    body = storage.open_archive(key)
    with open(destination, "wb") as handle:
        for chunk in body.iter_chunks():
            handle.write(chunk)


def _rewrap(source, target, identity, recipients):
    """age -d (old identity) | age -r ... (current keys); the plaintext only ever streams."""
    decrypt = subprocess.Popen(["age", "--decrypt", "-i", str(identity), str(source)],
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    args = ["age"]
    for item in recipients:
        args += ["-r", item["public_recipient"]]
    encrypt = subprocess.run([*args, "-o", str(target)], stdin=decrypt.stdout, stderr=subprocess.DEVNULL)
    decrypt.stdout.close()
    if decrypt.wait() != 0 or encrypt.returncode != 0:
        raise KeyRotationError("reencrypt_failed", "The archive could not be re-encrypted.")


def reencrypt_archive(row, *, actor=None, identity_file=None):
    if not can_reencrypt(row, identity_file):
        raise KeyRotationError("not_reencryptable", "Only a one-space archive this server can open can be re-encrypted.")
    recipients = selection_for(row)
    identity = identity_file or settings.TENANT_MIGRATION_AGE_IDENTITY_FILE
    new_key = f"backup-archives/{row.scope}/{row.pk}.reencrypted-{uuid.uuid4().hex[:12]}.tar.age"
    with tempfile.TemporaryDirectory(prefix="spaceworks-reencrypt-") as workdir:
        source, target, check = (Path(workdir, name) for name in ("old.age", "new.age", "check.age"))
        _download(row.object_key, source)
        if _sha256(source) != row.archive_sha256:
            raise KeyRotationError("archive_digest_mismatch", "The stored archive does not match its recorded digest.")
        _rewrap(source, target, identity, recipients)
        digest, size = _sha256(target), target.stat().st_size
        storage.upload_archive(new_key, target)
        _download(new_key, check)
        if _sha256(check) != digest:
            storage.delete_archive(new_key)
            raise KeyRotationError("reencrypt_unverified", "The re-encrypted archive did not read back intact.")
    with transaction.atomic():
        locked = BackupArchive.objects.select_for_update().get(pk=row.pk)
        if locked.archive_sha256 != row.archive_sha256 or locked.status != BackupArchive.Status.AVAILABLE:
            transaction.on_commit(lambda: storage.delete_archive(new_key))
            return locked
        old_key = locked.object_key
        manifest = dict(locked.manifest or {})
        manifest["recipients"] = recipients
        manifest["reencrypted_at"] = timezone.now().isoformat()
        locked.object_key, locked.archive_sha256, locked.size_bytes, locked.manifest = new_key, digest, size, manifest
        locked.save(update_fields=["object_key", "archive_sha256", "size_bytes", "manifest", "updated_at"])
        audit.record(actor, "backup.reencrypted", makerspace=locked.makerspace, target=locked,
                     meta={"scope": locked.scope, "size_bytes": size})
        transaction.on_commit(lambda: storage.delete_archive(old_key))
    return locked


def purge_archive(row, *, actor=None):
    """Delete a stale archive's bytes now; the row stays only if a restore names it."""
    for key in (row.object_key, row.staging_object_key, storage.staging_locator(row.pk)):
        if key and not storage.delete_archive(key):
            raise KeyRotationError("purge_failed", "The archive bytes could not be deleted; try again.")
    storage.delete_archive_prefix(f"backup-archives/staging/{row.pk}/")
    with transaction.atomic():
        locked = BackupArchive.objects.select_for_update().get(pk=row.pk)
        ledger = BackupArtifactLedger.objects.filter(pk=locked.pk).first()
        if ledger and ledger.state in {BackupArtifactLedger.State.AVAILABLE, BackupArtifactLedger.State.SUPERSEDED}:
            mark_managed_bytes_deleted(ledger.artifact_id)
        kept = locked.restores.exists()
        audit.record(actor, "backup.purged", makerspace=locked.makerspace, target=locked,
                     meta={"scope": locked.scope, "row_kept_for_restore_history": kept})
        if kept:
            locked.status, locked.size_bytes = BackupArchive.Status.EXPIRED, 0
            locked.save(update_fields=["status", "size_bytes", "updated_at"])
        else:
            locked.delete()


def run_requested_reencryption(limit=BATCH):
    """One bounded batch of the re-encryption a superadmin requested; clears itself when done."""
    from .models import PlatformBackupSettings
    if PlatformBackupSettings.load().reencrypt_requested_at is None:
        return 0
    pending = [row for row in stale_archives() if can_reencrypt(row)]
    done = 0
    for row in pending[:limit]:
        try:
            reencrypt_archive(row)
            done += 1
        except Exception:  # one bad archive never blocks the rest; it stays listed as stale
            continue
    if len(pending) <= limit:
        PlatformBackupSettings.objects.filter(pk=1).update(reencrypt_requested_at=None)
    return done
