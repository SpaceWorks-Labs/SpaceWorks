"""Scheduled restore drills (release 2 L11, BK-10/BK-91, #76, #128 C-22).

A drill proves a space's latest backup really restores, without touching anything live:

1. A THROWAWAY age identity is generated in the drill's private temporary directory.
2. The archive's ciphertext is copied from the bucket (read only). This server's live
   restore identity is READ in place by ``age --decrypt`` -- never copied, written or
   re-wrapped -- and the plaintext streams straight into a re-encryption to the
   throwaway key. From here on only the throwaway identity is used.
3. B2's pipeline opens the drill copy (``decrypted_archive`` with the throwaway identity,
   ``SpaceArchive`` and the same space/format/deployment validation as a real restore).
4. ``restore_drill_checks`` rebuilds every archived row in an ISOLATED scratch database
   (its own name and connection alias, never the live one) and verifies every archived
   object's bytes locally. Nothing is uploaded to any bucket.
5. The scratch database is dropped and the temporary directory (with the throwaway
   identity and every decrypted byte) is deleted, success or failure. Only the report's
   counts and typed outcome remain; a failure notifies the superadmin.
"""
import logging
import subprocess
import tempfile
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.db.models import Max
from django.test.utils import override_settings
from django.utils import timezone

from apps.audit import services as audit

from .archive_reencrypt import _download, _rewrap, _sha256
from .models import BackupArchive, PlatformBackupSettings
from .models_drill import RestoreDrillReport
from .space_restore_plan import READABLE_FORMATS, SpaceArchive, SpaceRestoreError

logger = logging.getLogger(__name__)


def throwaway_identity(workdir):
    identity = Path(workdir, "drill-identity.txt")
    subprocess.run(["age-keygen", "-o", str(identity)], check=True, capture_output=True)
    recipient = subprocess.run(["age-keygen", "-y", str(identity)], check=True, capture_output=True,
                               text=True).stdout.strip()
    return identity, recipient


def due_archive(now=None):
    """The newest restorable archive of the space whose last drill is oldest, or None."""
    row = PlatformBackupSettings.load()
    days = row.restore_drill_interval_days
    if not days:
        return None
    if not (settings.TENANT_MIGRATION_AGE_IDENTITY_FILE and settings.TENANT_MIGRATION_AGE_RECIPIENT):
        return None
    now = now or timezone.now()
    last = dict(RestoreDrillReport.objects.values("makerspace_id_snapshot")
                .annotate(at=Max("started_at")).values_list("makerspace_id_snapshot", "at"))
    archives = BackupArchive.objects.filter(
        scope=BackupArchive.Scope.MAKERSPACE, status=BackupArchive.Status.AVAILABLE,
        format__in=READABLE_FORMATS, makerspace__isnull=False, manifest__server_restorable=True,
    ).order_by("makerspace_id", "-completed_at").distinct("makerspace_id")
    due = [item for item in archives if last.get(item.makerspace_id) is None
           or last[item.makerspace_id] <= now - timedelta(days=days)]
    due.sort(key=lambda item: (last.get(item.makerspace_id) is not None, last.get(item.makerspace_id) or now))
    return due[0] if due else None


def run_due_drill():
    archive = due_archive()
    return run_drill(archive) if archive is not None else None


def run_drill(archive, *, actor=None):
    from apps.tenant_migration.import_staging import decrypted_archive
    from .restore_drill_checks import reconstruct
    from .space_restore_staging import _validated

    started, checks, error = timezone.now(), {}, None
    try:
        with tempfile.TemporaryDirectory(prefix="spaceworks-drill-") as workdir:
            identity, recipient = throwaway_identity(workdir)
            live_copy, drill_copy = Path(workdir, "archive.age"), Path(workdir, "drill.age")
            _download(archive.object_key, live_copy)
            if _sha256(live_copy) != archive.archive_sha256:
                raise SpaceRestoreError("archive_digest_mismatch", "The stored archive does not match its digest.")
            _rewrap(live_copy, drill_copy, settings.TENANT_MIGRATION_AGE_IDENTITY_FILE,
                    [{"public_recipient": recipient}])
            live_copy.unlink()
            with override_settings(TENANT_MIGRATION_AGE_IDENTITY_FILE=str(identity),
                                   TENANT_MIGRATION_AGE_RECIPIENT=recipient):
                with decrypted_archive(drill_copy, require_carried_keys=False) as (root, _carried):
                    space_archive = _validated(SpaceArchive(root), archive, archive.makerspace)
                    checks = reconstruct(space_archive, workdir)
    except Exception as exc:  # every failure is a typed report, never a crash of the tick
        error = exc if isinstance(exc, SpaceRestoreError) else SpaceRestoreError(
            getattr(exc, "code", "drill_failed"), "The drill could not complete.")
        logger.warning("restore_drill_failed", extra={"archive_id": str(archive.pk), "error_code": error.code})
    return _record(archive, started, checks, error, actor)


def _record(archive, started, checks, error, actor):
    report = RestoreDrillReport.objects.create(
        makerspace=archive.makerspace, makerspace_id_snapshot=archive.makerspace_id, archive=archive,
        archive_id_snapshot=archive.pk, started_at=started, finished_at=timezone.now(),
        outcome=RestoreDrillReport.Outcome.FAILED if error else RestoreDrillReport.Outcome.PASSED,
        error_code=getattr(error, "code", "")[:48], error_detail=str(error or "")[:300], checks=checks,
    )
    if error:
        audit.record(actor, "backup.drill_failed", makerspace=archive.makerspace, target=report,
                     meta={"rows": checks.get("row_total", 0), "error_code": report.error_code})
    else:
        audit.record(actor, "backup.drill_completed", makerspace=archive.makerspace, target=report,
                     meta={"rows": checks.get("row_total", 0), "objects_verified": checks.get("objects_verified", 0)})
    if error:
        from .operator_notice import notify_drill_failed
        notify_drill_failed(report)
    return report
