"""Per-space restore lifecycle: request -> preview -> confirm -> apply (superadmin only).

Every transition is a row-locked compare-and-set on the operation and writes an audit row
in the restored space. The heavy steps (preview, apply) run in Celery; these functions
only move the journal and dispatch. The views own re-authentication and the typed slug.
"""

from django.utils.translation import gettext
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.platform_authority import is_platform_superadmin
from apps.audit import services as audit

from .models import BackupArchive, MakerspaceRestoreOperation as Op
from .space_restore_plan import SpaceRestoreError
from .space_restore_staging import require_restorable, require_server_identity

OPEN_FOR_ABORT = (Op.Stage.REQUESTED, Op.Stage.STAGING, Op.Stage.PREVIEW_READY)


def _require_superadmin(actor):
    if not is_platform_superadmin(actor):
        raise PermissionDenied(gettext("Only the platform superadmin restores a makerspace."))


def request_restore(actor, makerspace, archive):
    _require_superadmin(actor)
    try:
        require_server_identity()
        require_restorable(archive, makerspace)
    except SpaceRestoreError as exc:
        raise ValidationError({"detail": str(exc), "code": exc.code}) from None
    try:
        with transaction.atomic():
            snapshot_at = parse_datetime(str(archive.manifest.get("snapshot_at") or "")) or archive.completed_at
            op = Op.objects.create(makerspace=makerspace, archive=archive, requested_by=actor,
                                   snapshot_at=snapshot_at)
            audit.record(actor, "backup.space_restore_requested", makerspace=makerspace, target=op,
                         meta={"restore_id": str(op.pk), "archive_id": str(archive.pk), "source": op.source})
    except IntegrityError:
        raise ValidationError({"detail": gettext("This makerspace already has a restore in progress."),
                               "code": "restore_in_progress"}) from None
    from .tasks_space_restore import dispatch_preview
    dispatch_preview(op)
    return op


@transaction.atomic
def transition(op_id, expected, stage, **fields):
    """Compare-and-set one stage change; returns the locked row or None if it moved."""
    op = Op.objects.select_for_update().filter(pk=op_id, stage__in=expected).first()
    if op is None:
        return None
    op.stage = stage
    for name, value in fields.items():
        setattr(op, name, value)
    op.save()
    return op


def confirm_restore(actor, op, typed_slug):
    _require_superadmin(actor)
    if typed_slug != op.makerspace.slug:
        raise ValidationError({"detail": gettext("Type the makerspace's slug exactly to confirm."), "code": "confirmation_mismatch"})
    if op.preview.get("blocked"):
        raise ValidationError({"detail": gettext("Rows outside this space would be left pointing at removed rows."),
                               "code": "dangling_references"})
    moved = transition(op.pk, (Op.Stage.PREVIEW_READY,), Op.Stage.APPLYING, confirmed_by=actor,
                       progress={"step": "queued", "percent": 0})
    if moved is None:
        raise ValidationError({"detail": gettext("This restore is not waiting for confirmation."), "code": "stage_conflict"})
    audit.record(actor, "backup.space_restore_confirmed", makerspace=moved.makerspace, target=moved,
                 meta={"restore_id": str(moved.pk), "archive_id": str(moved.archive_id)})
    from .tasks_space_restore import dispatch_apply
    dispatch_apply(moved)
    return moved


def abort_restore(actor, op):
    _require_superadmin(actor)
    previous = op.stage
    moved = transition(op.pk, OPEN_FOR_ABORT, Op.Stage.ABORTED, finished_at=timezone.now())
    if moved is None:
        raise ValidationError({"detail": gettext("Only a restore that has not started applying can be cancelled."),
                               "code": "stage_conflict"})
    audit.record(actor, "backup.space_restore_aborted", makerspace=moved.makerspace, target=moved,
                 meta={"restore_id": str(moved.pk), "stage": previous})
    return moved


def fail(op_id, stage_from, error, actor=None):
    code = getattr(error, "code", "restore_failed")
    detail = str(error).strip()[:500] or "The restore failed."
    moved = transition(op_id, stage_from, Op.Stage.FAILED, error_code=code, error_detail=detail,
                       finished_at=timezone.now())
    if moved is not None:
        audit.record(actor, "backup.space_restore_failed", makerspace=moved.makerspace, target=moved,
                     meta={"restore_id": str(moved.pk), "stage": stage_from[0], "error_code": code})
        from .space_restore_notifications import notify_outcome
        notify_outcome(moved)
    return moved


def restore_points(makerspace):
    return BackupArchive.objects.filter(
        scope=BackupArchive.Scope.MAKERSPACE, makerspace=makerspace, status=BackupArchive.Status.AVAILABLE,
    ).order_by("-completed_at")
