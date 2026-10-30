"""Open one per-space archive with this server's restore key, for one step only.

The ciphertext is copied from the private bucket, decrypted with
``TENANT_MIGRATION_AGE_IDENTITY_FILE`` into a temporary directory and checked against
the restore's makerspace and this deployment. Everything decrypted is deleted when the
step ends, success or failure (#50b): preview and apply each open the archive again.
"""

from contextlib import contextmanager
import tempfile
from pathlib import Path

from django.conf import settings

from apps.tenant_migration.insertion_errors import ArchiveFormatError

from . import storage
from .space_restore_plan import FORMAT, SpaceArchive, SpaceRestoreError


def require_server_identity():
    if not (settings.TENANT_MIGRATION_AGE_IDENTITY_FILE and settings.TENANT_MIGRATION_AGE_RECIPIENT):
        raise SpaceRestoreError(
            "server_identity_missing",
            "This server has no restore key (TENANT_MIGRATION_AGE_IDENTITY_FILE and "
            "TENANT_MIGRATION_AGE_RECIPIENT), so it cannot open a one-space backup.",
        )


def require_restorable(archive_row, makerspace):
    if archive_row.scope != "makerspace" or archive_row.makerspace_id != makerspace.pk:
        raise SpaceRestoreError("wrong_space", "This restore point belongs to a different makerspace.")
    if archive_row.status != "available":
        raise SpaceRestoreError("archive_unavailable", "This restore point is not available.")
    if archive_row.format != FORMAT or not archive_row.manifest.get("server_restorable"):
        raise SpaceRestoreError(
            "archive_not_restorable",
            "This backup cannot be restored in the app; it was not encrypted to this server's restore key.",
        )


@contextmanager
def opened_space_archive(archive_row, makerspace):
    require_server_identity()
    require_restorable(archive_row, makerspace)
    from apps.tenant_migration.import_staging import decrypted_archive

    with tempfile.TemporaryDirectory(prefix="spaceworks-space-restore-") as workdir:
        encrypted = Path(workdir, "archive.tar.age")
        try:
            body = storage.open_archive(archive_row.object_key)
            with encrypted.open("wb") as handle:
                for chunk in body.iter_chunks():
                    handle.write(chunk)
        except storage.BackupStorageError:
            raise SpaceRestoreError("archive_unavailable", "The restore point's bytes could not be read.") from None
        try:
            with decrypted_archive(encrypted, require_carried_keys=False) as (root, _carried):
                encrypted.unlink()
                yield _validated(SpaceArchive(root), archive_row, makerspace)
        except ArchiveFormatError as exc:
            raise SpaceRestoreError("archive_unreadable", str(exc)) from None


def _validated(archive, archive_row, makerspace):
    from apps.tenant_migration.deployment_keys import public_deployment_identity

    manifest = archive.manifest
    if archive.makerspace_id != makerspace.pk or manifest.get("archive_id") != str(archive_row.pk):
        raise SpaceRestoreError("wrong_space", "The decrypted archive does not match this restore point.")
    if manifest.get("payload_format") != FORMAT:
        raise SpaceRestoreError("archive_not_restorable", "The archive payload format is not supported.")
    if manifest.get("deployment_id") != public_deployment_identity()["deployment_id"]:
        raise SpaceRestoreError(
            "other_deployment", "This archive was made on another deployment; use tenant migration instead.",
        )
    return archive
