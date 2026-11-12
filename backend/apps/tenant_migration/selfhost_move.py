"""The self-host move (release 2 L11, BK-90; #111 Q2/Q7, #128 C-18/C-23, #137 Q-B1, #160).

1. A Space Manager REQUESTS a move with a note and reads its status. Nothing else: no
   download, no recipient, no export of their own (#111 Q2).
2. The superadmin approves (or rejects) it in /control/, then RUNS the export there with
   a one-shot age recipient the target operator supplied. The archive is the PORTABLE
   tenant-migration archive (format 2) -- the path that carries U-D's credential block,
   so staff AND members keep their sign-in on the target (#160) -- encrypted to that
   one-shot key plus the platform key (#111 Q7). Running it approves the space's full
   identity closure in the same superadmin act (everyone moves with their space).
3. The target operator imports it on a fresh self-host install with
   ``manage.py import_portable_tenant_dump`` through the ordinary admission and
   identity-decision flow.

Every step is audited (``selfhost_move.*``); the space's Space Managers are told of each
status change and the superadmins of a new request.
"""
from django.utils.translation import gettext
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError

from apps.audit import services as audit

from .models_selfhost_move import SelfHostMoveRequest

Status = SelfHostMoveRequest.Status


class MoveConflict(APIException):
    status_code = 409

    def __init__(self, code, detail):
        super().__init__({"detail": detail, "code": code}, code)


def latest_request(makerspace):
    return SelfHostMoveRequest.objects.filter(makerspace=makerspace).first()


def request_move(actor, makerspace, note=""):
    try:
        with transaction.atomic():
            move = SelfHostMoveRequest.objects.create(makerspace=makerspace, requested_by=actor,
                                                      note=str(note or "").strip()[:2000])
            audit.record(actor, "selfhost_move.requested", makerspace=makerspace, target=move,
                         meta={"status": move.status})
    except IntegrityError:
        raise MoveConflict("move_request_exists", gettext("This space already has an open move request.")) from None
    from .selfhost_move_notifications import notify_requested, notify_status
    notify_requested(move)
    notify_status(move)
    return move


def _locked(move, *expected):
    locked = SelfHostMoveRequest.objects.select_for_update().select_related("makerspace").get(pk=move.pk)
    if locked.status not in expected:
        code = "move_not_approved" if Status.APPROVED in expected else "move_request_closed"
        raise MoveConflict(code, gettext("This move request is %(status)s.") % {"status": locked.get_status_display().lower()})
    return locked


def decide(actor, move, *, approve, note=""):
    _require_superadmin(actor)
    with transaction.atomic():
        locked = _locked(move, Status.REQUESTED)
        locked.status = Status.APPROVED if approve else Status.REJECTED
        locked.decided_by, locked.decided_at = actor, timezone.now()
        locked.decision_note = str(note or "").strip()[:500]
        locked.save(update_fields=["status", "decided_by", "decided_at", "decision_note", "updated_at"])
        if approve:
            audit.record(actor, "selfhost_move.approved", makerspace=locked.makerspace, target=locked,
                         meta={"status": locked.status})
        else:
            audit.record(actor, "selfhost_move.rejected", makerspace=locked.makerspace, target=locked,
                         meta={"status": locked.status})
    from .selfhost_move_notifications import notify_status
    notify_status(locked)
    return locked


def canonical_one_shot_recipient(raw):
    from apps.backup.age_recipients import canonical_recipient, fingerprint_for
    try:
        value = canonical_recipient(raw)
    except DjangoValidationError:
        raise ValidationError({"recipient": gettext("Paste the target server's age public key (age1...).")},
                              code="recipient_key_invalid") from None
    if not settings.BACKUP_AGE_RECIPIENT:
        raise MoveConflict("platform_key_missing", gettext("BACKUP_AGE_RECIPIENT must be configured before a move export."))
    if value == str(settings.BACKUP_AGE_RECIPIENT).strip().lower():
        raise ValidationError({"recipient": gettext("Use the target server's own key, not the platform key.")},
                              code="recipient_key_invalid")
    return value, fingerprint_for(value)


def start_export(actor, move, recipient):
    """Claim the export (approved -> exporting) and hand it to the worker."""
    _require_superadmin(actor)
    value, fingerprint = canonical_one_shot_recipient(recipient)
    try:
        with transaction.atomic():
            # A failed export may be run again with a (possibly new) target key.
            locked = _locked(move, Status.APPROVED, Status.FAILED)
            locked.status, locked.recipient_fingerprint, locked.failure_code = Status.EXPORTING, fingerprint, ""
            locked.save(update_fields=["status", "recipient_fingerprint", "failure_code", "updated_at"])
            audit.record(actor, "selfhost_move.export_started", makerspace=locked.makerspace, target=locked,
                         meta={"status": locked.status, "recipient_fingerprint": fingerprint})
            transaction.on_commit(lambda: _dispatch(locked.pk, value, actor.pk))
    except IntegrityError:
        raise MoveConflict("move_request_exists", gettext("This space already has another open move request.")) from None
    return locked


def _dispatch(move_id, recipient, actor_id):
    from .tasks import run_selfhost_move_export_task
    run_selfhost_move_export_task.delay(str(move_id), recipient, actor_id)


def run_export(move_id, recipient, actor_id):
    from apps.accounts.models import User
    from .admission import approve_closure, compute_pending_closure
    from .archive_envelope import build_tenant_migration_archive

    move = SelfHostMoveRequest.objects.select_related("makerspace").get(pk=move_id)
    if move.status != Status.EXPORTING:
        return move
    actor = User.objects.get(pk=actor_id)
    output = Path(settings.BACKUP_OPS_DIR, "selfhost-moves", f"{move.pk}.tar.age")
    try:
        _require_superadmin(actor)
        output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        output.unlink(missing_ok=True)
        closure = compute_pending_closure(move.makerspace)
        approval = approve_closure(actor=actor, makerspace=move.makerspace, digest=closure["digest"], decisions=[
            {"user_id": item["id"], "approved": True} for item in closure["identities"]])
        _path, _manifest, digest = build_tenant_migration_archive(
            move.makerspace, output, actor=actor, disclosure_approval=approval,
            recipient=[recipient, settings.BACKUP_AGE_RECIPIENT])
    except Exception as exc:
        output.unlink(missing_ok=True)
        return _finish(move.pk, actor, failure=getattr(exc, "code", None) or "export_failed")
    return _finish(move.pk, actor, path=str(output), digest=digest)


def _finish(move_id, actor, *, path="", digest="", failure=""):
    with transaction.atomic():
        move = SelfHostMoveRequest.objects.select_for_update().select_related("makerspace").get(pk=move_id)
        move.status = Status.FAILED if failure else Status.EXPORTED
        move.artifact_path, move.artifact_sha256 = path, digest
        move.failure_code, move.exported_at = str(failure)[:48], None if failure else timezone.now()
        move.save(update_fields=["status", "artifact_path", "artifact_sha256", "failure_code", "exported_at",
                                 "updated_at"])
        if failure:
            audit.record(actor, "selfhost_move.export_failed", makerspace=move.makerspace, target=move,
                         meta={"status": move.status, "failure_code": move.failure_code})
        else:
            audit.record(actor, "selfhost_move.exported", makerspace=move.makerspace, target=move,
                         meta={"status": move.status, "artifact_sha256": digest})
    from .selfhost_move_notifications import notify_status
    notify_status(move)
    return move


def discard_artifact(actor, move):
    _require_superadmin(actor)
    with transaction.atomic():
        locked = SelfHostMoveRequest.objects.select_for_update().get(pk=move.pk)
        if locked.artifact_path:
            Path(locked.artifact_path).unlink(missing_ok=True)
            locked.artifact_path = ""
            locked.save(update_fields=["artifact_path", "updated_at"])
            audit.record(actor, "selfhost_move.artifact_discarded", makerspace=locked.makerspace, target=locked,
                         meta={"status": locked.status})
    return locked


def _require_superadmin(actor):
    from .services_import_job import _require_superadmin as require
    require(actor)
