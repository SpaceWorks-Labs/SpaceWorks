"""The two heavy steps of a per-space restore, run by Celery.

Preview opens the archive, computes the read-only preview and stores it with the live
fingerprint. Apply takes a mandatory safety backup of the live space first (Q16; a
failed safety backup refuses the restore), closes the space's source gate, re-checks the
fingerprint and runs ``apply_space_restore`` in ONE transaction, then restores object
bytes, reopens the gate, audits and notifies (Q15). The deployment must be NORMAL.
"""

import logging
import uuid

from django.utils import timezone

from .models import BackupArchive, DeploymentRecoveryState, MakerspaceRestoreOperation as Op
from .space_restore_plan import SpaceRestoreError
from apps.audit import services as audit

from .space_restore_services import fail, transition

logger = logging.getLogger(__name__)


def run_preview(op_id):
    op = transition(op_id, (Op.Stage.REQUESTED,), Op.Stage.STAGING, progress={"step": "preview", "percent": 10})
    if op is None:
        return None
    from .space_restore_preview import compute_preview, live_fingerprint
    from .space_restore_staging import opened_space_archive
    try:
        with opened_space_archive(op.archive, op.makerspace) as archive:
            preview = compute_preview(op.makerspace, archive)
            fingerprint = live_fingerprint(op.makerspace)
    except Exception as exc:
        logger.exception("space_restore_preview_failed", extra={"restore_id": str(op_id)})
        return fail(op_id, (Op.Stage.STAGING,), _typed(exc))
    op = transition(op_id, (Op.Stage.STAGING,), Op.Stage.PREVIEW_READY, preview=preview,
                    preview_fingerprint=fingerprint, preview_ready_at=timezone.now(),
                    progress={"step": "preview_ready", "percent": 20})
    if op is not None:
        audit.record(op.requested_by, "backup.space_restore_preview_ready", makerspace=op.makerspace, target=op,
                     meta={"restore_id": str(op.pk), "removed_rows": preview["totals"]["removed_rows"],
                           "added_rows": preview["totals"]["added_rows"],
                           "blocking_count": preview["blocking_count"],
                           "money_after_restore_point": len(preview["money_after_restore_point"])})
    return op


def run_apply(op_id):
    op = Op.objects.select_related("makerspace", "archive").get(pk=op_id)
    if op.stage != Op.Stage.APPLYING or op.applied_at is not None:
        return op
    Op.objects.filter(pk=op_id).update(applied_at=timezone.now())
    try:
        safety = _safety_backup(op)
        _progress(op_id, "restoring", 50, safety_archive=safety)
        report = _apply_and_restore_objects(op)
    except Exception as exc:
        logger.exception("space_restore_apply_failed", extra={"restore_id": str(op_id)})
        return fail(op_id, (Op.Stage.APPLYING,), _typed(exc), actor=op.confirmed_by)
    done = transition(op_id, (Op.Stage.APPLYING,), Op.Stage.COMPLETED, report=report,
                      finished_at=timezone.now(), progress={"step": "completed", "percent": 100})
    if done is not None:
        audit.record(done.confirmed_by, "backup.space_restore_completed", makerspace=done.makerspace,
                     target=done, meta={
                         "restore_id": str(done.pk), "archive_id": str(done.archive_id),
                         "safety_archive_id": str(done.safety_archive_id),
                         "removed_rows": sum(report["removed"].values()),
                         "restored_rows": sum(report["restored"].values()),
                         "money_after_restore_point": len(report["money_after_restore_point"]),
                         "objects_restored": report.get("objects_restored", 0)})
        from .space_restore_notifications import notify_outcome
        notify_outcome(done)
    return done


def _safety_backup(op):
    """A fresh archive of the live space; the restore refuses if it does not complete."""
    from .services import create_archive, run_archive
    archive = create_archive(op.confirmed_by, scope=BackupArchive.Scope.MAKERSPACE,
                             makerspace=op.makerspace, trigger=BackupArchive.Trigger.SAFETY)
    _progress(op.pk, "safety_backup", 30, safety_archive=archive)
    result = run_archive(archive.pk)
    if result is None or result.status != BackupArchive.Status.AVAILABLE:
        raise SpaceRestoreError("safety_backup_failed", "The safety backup of the live space did not complete.")
    return result


def _apply_and_restore_objects(op):
    """ONE transaction inside the closed source gate, then the bytes after it commits."""
    from apps.tenant_migration.source_gate import quiesced_snapshot, reopen_after_verified_abort
    from .space_restore_apply import apply_space_restore
    from .space_restore_objects import delete_unreferenced, referenced_keys, restore_objects
    from .space_restore_plan import MONEY_LABELS
    from .space_restore_preview import live_fingerprint, rows_after_restore_point
    from .space_restore_staging import opened_space_archive

    space = op.makerspace
    owner_id = uuid.uuid4()
    with opened_space_archive(op.archive, space) as archive:
        try:
            with quiesced_snapshot(space, op.confirmed_by, owner_id=owner_id):
                state = DeploymentRecoveryState.load()
                if state.mode != DeploymentRecoveryState.Mode.NORMAL or state.active_restore_id:
                    raise SpaceRestoreError("deployment_busy", "A whole-platform restore or quiescence is active.")
                locked = space.__class__.objects.select_for_update().get(pk=space.pk)
                if live_fingerprint(locked) != op.preview_fingerprint:
                    raise SpaceRestoreError("live_drift", "The space changed after the preview; preview it again.")
                money = rows_after_restore_point(locked, MONEY_LABELS, op.snapshot_at)
                keys_before = referenced_keys(space.pk)
                report = apply_space_restore(locked, archive)
                from apps.data_export.loan_context_integrity import validate_loan_context_import
                validate_loan_context_import(locked.pk)
                from apps.makerspaces.loan_context_generations import rotate
                rotate(locked)
                from .station_revocation import revoke_station_credentials
                report["station_credentials_revoked"] = revoke_station_credentials(
                    makerspace=locked, actor=op.confirmed_by)
        finally:
            # Reopen only the gate THIS restore closed, never another migration's.
            from apps.tenant_migration.models_source_gate import SourceMigrationGate
            if SourceMigrationGate.objects.filter(makerspace=space, owner_id=owner_id).exists():
                reopen_after_verified_abort(space, op.confirmed_by)
        report["money_after_restore_point"] = money
        _progress(op.pk, "objects", 80)
        restored = restore_objects(archive, op.pk)
        archived = restored.pop("archived")
        report.update(restored)
        report.update(delete_unreferenced(keys_before, referenced_keys(space.pk), archived))
    return report


def _progress(op_id, step, percent, **fields):
    Op.objects.filter(pk=op_id).update(progress={"step": step, "percent": percent}, **fields)


def _typed(exc):
    if isinstance(exc, SpaceRestoreError):
        return exc
    return SpaceRestoreError("restore_failed", "The restore could not complete; nothing was changed.")
