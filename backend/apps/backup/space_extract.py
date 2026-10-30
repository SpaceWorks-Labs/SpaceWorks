"""Extract ONE space from a decrypted whole-platform backup as a per-space restore point.

Owner decision #144: the operator decrypts the whole-platform archive ON THE HOST with the
offline platform key (the server never receives that key) and points this at the
decrypted directory. The space's raw slice is read from a scratch copy of the archived
database, migrated to this code's schema, packaged with its object bytes exactly like a
nightly one-space archive, encrypted to the platform key AND this server's restore key,
and registered as an ordinary restore point. The app then restores it through the usual
preview and confirm. Every refusal happens before anything is written.
"""

import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import uuid
from datetime import timedelta
from pathlib import Path

from django.core.management import call_command
from django.db import connections, transaction
from django.utils import timezone

from apps.audit import services as audit

from . import age_recipients, storage
from .digests import SUPPORTED_ARCHIVE_FORMATS, build_content_ledger, sha256_file
from .models import BackupArchive, PlatformBackupSettings
from .space_restore_plan import FORMAT, SpaceRestoreError

AGE_IDENTITY_MARKER = "AGE-SECRET-KEY-"


def extract_space_restore_point(actor, source_dir, makerspace):
    """Return the new AVAILABLE BackupArchive for ``makerspace`` from ``source_dir``."""
    from apps.accounts.platform_authority import is_platform_superadmin

    if not is_platform_superadmin(actor):
        raise SpaceRestoreError("not_superadmin", "Only a platform superadmin account may extract a restore point.")
    root = _validated_source(Path(source_dir), makerspace)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if age_recipients.server_recipient() is None:
        raise SpaceRestoreError("server_identity_missing", "TENANT_MIGRATION_AGE_RECIPIENT is not configured.")
    with tempfile.TemporaryDirectory(prefix="spaceworks-space-extract-") as workdir:
        bundle = Path(workdir, "bundle")
        object_keys = _slice_from_scratch(root / "database.dump", makerspace.pk, bundle / "tenant")
        objects = _copy_objects(root, manifest, object_keys, bundle / "objects")
        archive_id = uuid.uuid4()
        recipients = [age_recipients.platform_recipient(), age_recipients.server_recipient()]
        space_manifest = _manifest(archive_id, makerspace, manifest, objects, recipients)
        space_manifest["contents"] = build_content_ledger(bundle)
        (bundle / "manifest.json").write_text(json.dumps(space_manifest, sort_keys=True, default=str),
                                              encoding="utf-8")
        encrypted = _encrypt(bundle, Path(workdir), recipients)
        return _register(actor, makerspace, archive_id, encrypted, space_manifest, manifest)


def _validated_source(root, makerspace):
    if root.is_symlink() or not root.is_dir():
        raise SpaceRestoreError("unsafe_input", "The source must be a real directory, not a link.")
    root = root.resolve()
    for path in root.rglob("*"):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise SpaceRestoreError("unsafe_input", f"The source contains a link or special file: {path.name}.")
        if path.is_file() and path.suffix in {".key", ".txt"} and _looks_like_identity(path):
            raise SpaceRestoreError("unsafe_input", "Remove the age identity from the source; it must stay offline.")
    for required in ("manifest.json", "database.dump"):
        if not (root / required).is_file():
            raise SpaceRestoreError("archive_unreadable", f"The decrypted archive has no {required}.")
    try:
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise SpaceRestoreError("archive_unreadable", "manifest.json is unreadable.") from None
    if manifest.get("scope") != BackupArchive.Scope.DEPLOYMENT or manifest.get("format") not in SUPPORTED_ARCHIVE_FORMATS:
        raise SpaceRestoreError("wrong_scope", "This is not a whole-platform archive.")
    if manifest.get("partial"):
        raise SpaceRestoreError("archive_not_restorable", "A partial (legacy sovereign) archive cannot be extracted.")
    if makerspace.pk not in [int(value) for value in manifest.get("covered_makerspace_ids", [])]:
        raise SpaceRestoreError("wrong_space", "This archive does not cover that makerspace.")
    return root


def _looks_like_identity(path):
    try:
        with path.open("rb") as handle:
            return AGE_IDENTITY_MARKER.encode() in handle.read(4096)
    except OSError:
        return False


def _slice_from_scratch(dump, makerspace_id, destination):
    from .archive_payload import _tenant_payload
    from .projection_databases import restore_dump, temporary_database

    with temporary_database("space_extract") as (alias, name):
        restore_dump(dump, name)
        _require_known_migrations(alias)
        call_command("migrate", database=alias, interactive=False, verbosity=0)
        try:
            return _tenant_payload(makerspace_id, destination, using=alias)
        finally:
            connections[alias].close()


def _require_known_migrations(alias):
    from django.db.migrations.loader import MigrationLoader

    known = set(MigrationLoader(None, ignore_no_migrations=True).disk_migrations)
    with connections[alias].cursor() as cursor:
        cursor.execute("SELECT app, name FROM django_migrations")
        applied = set(cursor.fetchall())
    if applied - known:
        raise SpaceRestoreError("archive_newer_than_code",
                                "The archive was made by a newer release; upgrade before extracting.")


def _copy_objects(root, manifest, object_keys, destination):
    wanted = {(kind, key) for kind, keys in object_keys.items() for key in keys}
    copied = []
    for item in manifest.get("storage", {}).get("objects", []):
        identity = (item.get("bucket_kind"), item.get("key"))
        if identity not in wanted:
            continue
        copied.append(item)
        if item.get("retention_state") == "expired":
            continue
        source = (root / "objects" / identity[0] / identity[1]).resolve()
        if root not in source.parents or not source.is_file():
            raise SpaceRestoreError("archive_unreadable", f"Archived object {identity[1]!r} is missing.")
        target = destination / identity[0] / identity[1]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    missing = wanted - {(item.get("bucket_kind"), item.get("key")) for item in copied}
    if missing:
        raise SpaceRestoreError("archive_unreadable", f"{len(missing)} object(s) the space references are not in the archive.")
    return copied


def _manifest(archive_id, makerspace, manifest, objects, recipients):
    from apps.tenant_migration.deployment_keys import public_deployment_identity
    return {
        "format": "spaceworks-phase5a-v3", "archive_id": str(archive_id), "scope": "makerspace",
        "makerspace_id": makerspace.pk, "recipients": recipients, "covered_makerspace_ids": [makerspace.pk],
        "excluded_makerspace_ids": [], "partial": False, "snapshot_at": manifest.get("snapshot_at"),
        "payload_format": FORMAT, "trigger": BackupArchive.Trigger.EXTRACTED,
        "deployment_id": public_deployment_identity()["deployment_id"], "server_restorable": True,
        "extracted_from": {"archive_id": manifest.get("archive_id"), "snapshot_at": manifest.get("snapshot_at")},
        "storage": {"objects": objects}, "age_encrypted": True,
    }


def _encrypt(bundle, workdir, recipients):
    plain, encrypted = workdir / "space.tar", workdir / "space.tar.age"
    with tarfile.open(plain, "w") as tar:
        tar.add(bundle, arcname=".")
    command = ["age"]
    for entry in recipients:
        command += ["-r", entry["public_recipient"]]
    try:
        subprocess.run([*command, "-o", str(encrypted), str(plain)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    except (OSError, subprocess.CalledProcessError):
        raise SpaceRestoreError("encryption_failed", "The restore point could not be encrypted.") from None
    finally:
        plain.unlink(missing_ok=True)
    return encrypted


def _register(actor, makerspace, archive_id, encrypted, space_manifest, source_manifest):
    object_key = f"backup-archives/makerspace/{archive_id}.tar.age"
    storage.upload_archive(object_key, encrypted)
    size, digest, now = os.path.getsize(encrypted), sha256_file(encrypted), timezone.now()
    try:
        with transaction.atomic():
            archive = BackupArchive.objects.create(
                id=archive_id, scope=BackupArchive.Scope.MAKERSPACE, makerspace=makerspace, requested_by=actor,
                status=BackupArchive.Status.AVAILABLE, object_key=object_key, manifest=space_manifest,
                size_bytes=size, archive_sha256=digest, age_encrypted=True, format=FORMAT,
                trigger=BackupArchive.Trigger.EXTRACTED, started_at=now, completed_at=now,
                expires_at=now + timedelta(days=PlatformBackupSettings.load().retention_days),
            )
            audit.record(actor, "backup.space_restore_point_extracted", makerspace=makerspace, target=archive,
                         meta={"archive_id": str(archive.pk), "source_archive_id": str(source_manifest.get("archive_id")),
                               "size_bytes": size})
    except Exception:
        storage.delete_archive(object_key)
        raise
    return archive
