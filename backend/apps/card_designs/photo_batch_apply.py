"""Apply a reviewed photo batch, a few photos per Celery chunk (D314c addendum).

Each photo goes through the SAME path as a single staff upload: member and staff cards through
`member_card_storage.replace_photo_bytes` (re-encode, metadata stripped, storage charged, old object freed, the
photo-needs-update request resolved), event cards through `photos.attach_bytes` (which also records the consent).
The consent is the batch's `holders_consented` confirmation. The creator's authority is re-checked at every chunk,
so a revoked staff member's batch stops. "Remove backgrounds after upload" then queues one eraser job per photo.
"""
import logging

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import APIException

from apps.audit import services as audit

from . import cutouts, photo_batch_holders as roster
from .models_cutout import CardPhotoBatch, CardPhotoBatchItem
from .photo_batch import ATTACH
from .storage import delete_quietly, get_bytes

logger = logging.getLogger(__name__)
CHUNK = 10


def _member_card_for(kind, card):
    if kind != "staff_card":
        return card
    from apps.makerspaces.models import MemberCard
    return MemberCard.objects.filter(membership_id=card.membership_id, makerspace_id=card.makerspace_id,
                                     revoked_at__isnull=True).first()


def _attach(actor, kind, card, data):
    """-> the card kind and row that now hold the photo."""
    from . import photos
    if kind == "event_card":
        photos.attach_bytes(actor, "event_card", card, data, consent=True)
        return kind, card
    from apps.makerspaces.member_card_storage import replace_photo_bytes
    member = _member_card_for(kind, card)
    if member is None:
        raise LookupError("no_member_card")
    replace_photo_bytes(actor, member, data)
    photos.resolve_requests("member_card", member)
    return "member_card", member


def _apply_item(batch, space, event, item):
    card = roster.load_card(batch.kind, space, item.holder_id, event)
    data = get_bytes(item.file_key) if item.file_key else None
    if card is None:
        return "holder_gone"
    if not data:
        return "photo_missing"
    try:
        okind, ocard = _attach(batch.created_by, batch.kind, card, data)
    except LookupError as exc:
        return str(exc)
    audit.record(batch.created_by, "card_photo_batch.item_applied", makerspace=space, target=batch,
                 meta={"batch_id": batch.pk, "item_id": item.pk, "card_id": ocard.pk, "holder_kind": okind})
    if batch.remove_backgrounds:
        try:
            cutouts.request(batch.created_by, okind, ocard)
        except APIException as exc:  # limit reached, switch off, provider gone: the photo itself is still applied
            return _eraser_code(exc)
    return ""


def _eraser_code(exc):
    """A short, stable reason for the review table (the column holds 32 characters; codes were cut mid-word)."""
    code = str(getattr(exc, "code", None) or exc.default_code)
    if "quota" in code or "cutout_jobs" in code:
        return "eraser_limit_reached"
    known = {"not_found": "eraser_off", "eraser_not_configured": "eraser_not_configured", "eraser_opted_out": "eraser_opted_out"}
    return known.get(code, ("eraser_" + code)[:32])


def _finish(batch):
    items = batch.items.all()
    batch.applied_count = items.filter(state="applied").count()
    batch.failed_count = items.filter(state="failed").count()
    batch.skipped_count = items.filter(state="skipped").count()
    batch.state, batch.applied_at = CardPhotoBatch.State.DONE, timezone.now()
    batch.save()
    for item in items.exclude(file_key=""):
        delete_quietly(item.file_key)
    items.exclude(file_key="").update(file_key="")
    audit.record(batch.created_by, "card_photo_batch.finished", makerspace=batch.makerspace, target=batch,
                 meta={"batch_id": batch.pk, "holder_kind": batch.kind, "applied": batch.applied_count,
                       "skipped": batch.skipped_count, "failed": batch.failed_count})


def apply_chunk(batch_id):
    """-> True when more photos are waiting (the task re-queues itself)."""
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    batch = CardPhotoBatch.objects.select_related("makerspace", "created_by").filter(
        pk=batch_id, state=CardPhotoBatch.State.APPLYING).first()
    if batch is None:
        return False
    assert_write_allowed(batch.makerspace_id)
    try:
        space, event = roster.authorise(batch.created_by, batch.kind, batch.makerspace_id, batch.event_id)
    except Exception:  # authority lost since the batch was applied: nothing more is attached
        batch.items.filter(state="pending").update(state="skipped", error_code="not_authorised")
        _finish(batch)
        return False
    pending = list(batch.items.filter(state="pending").order_by("position")[:CHUNK])
    for item in pending:
        if item.decision not in ATTACH or not item.holder_id:
            item.state = CardPhotoBatchItem.State.SKIPPED
            item.save(update_fields=["state"])
            continue
        try:
            problem = _apply_item(batch, space, event, item)
        except Exception:
            logger.exception("photo_batch_item_failed")
            problem = "apply_failed"
        applied = not problem or problem.startswith("eraser_")
        item.state = CardPhotoBatchItem.State.APPLIED if applied else CardPhotoBatchItem.State.FAILED
        item.error_code = problem
        item.save(update_fields=["state", "error_code"])
        if item.file_key and applied:
            delete_quietly(item.file_key)
            item.file_key = ""
            item.save(update_fields=["file_key"])
    more = batch.items.filter(state="pending").exists()
    if not more:
        _finish(batch)
    return more


RESUME_CHUNKS = 20  # at most 200 photos per sweep per batch; a longer batch simply continues on the next sweep


def _resume(batch_id):
    """-> True when the batch was resumed without error (it may still have photos waiting for the next sweep)."""
    from apps.space_controls.write_policy import enforcing_read_only
    try:
        # Attaching photos creates records, so a read-only space refuses it here (a failed resume, then closed).
        with enforcing_read_only(), transaction.atomic():  # a savepoint: a failed resume rolls back its own half-chunk, nothing else
            for _ in range(RESUME_CHUNKS):
                if not apply_chunk(batch_id):
                    break
    except Exception:
        logger.exception("photo_batch_resume_failed", extra={"batch_id": batch_id})
        return False
    return True


def expire_stalled(limit=20):
    """A batch still applying at its expiry lost its worker (broker loss, crash). It is RESUMED first, under a row
    lock (``skip_locked``: a worker or another sweep already on it wins, so the chunk path stays single-flight);
    only a resume that fails closes it, so its temporary photos are deleted like every other batch's
    (`purge_expired_batches` skips applying batches): the remaining photos are skipped as `expired`. One tenant
    boundary per space (decision 337c)."""
    from apps.tenant_migration.gate_runtime import fanout_tenant_write
    counts, closed = {"skipped": 0}, 0
    stalled = CardPhotoBatch.objects.filter(state=CardPhotoBatch.State.APPLYING, expires_at__lte=timezone.now())
    for batch_id, space_id in list(stalled.order_by("pk").values_list("pk", "makerspace_id")[:limit]):
        with fanout_tenant_write(space_id, operation="card_photo_batch_expiry", counts=counts) as ok:
            if not ok:
                continue
            with transaction.atomic():
                batch = CardPhotoBatch.objects.select_for_update(skip_locked=True, of=("self",)).select_related(
                    "makerspace", "created_by").filter(pk=batch_id, state=CardPhotoBatch.State.APPLYING).first()
                if batch is None:  # locked by another worker, or it finished meanwhile
                    continue
                if _resume(batch.pk):
                    continue
                batch.refresh_from_db()
                batch.items.filter(state="pending").update(state="skipped", error_code="expired")
                _finish(batch)
                closed += 1
    return closed
