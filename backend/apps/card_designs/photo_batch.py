"""Bulk photo upload, matched to holders by file name (D314c addendum): create, add files, review, choose, apply.

Flow: staff create a batch (and confirm the holders agreed), add photos (files or a zip) in one or more requests,
review the table (matched / ambiguous / unmatched / holder already has a photo), choose, then apply. Applying goes
through the normal card-photo path (`photo_batch_apply`), one bounded Celery chunk at a time. Every file is a
private object under `card-photo-batches/` until applied or expired (7 days); the batch itself is audited once at
creation, once at apply and once at the end, and each applied photo has its own row.
"""
import uuid
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext
from rest_framework.exceptions import NotFound, ValidationError

from apps.audit import services as audit

from . import photo_batch_holders as roster
from .image_adapter import provider
from .images import normalise
from .models_cutout import CardPhotoBatch, CardPhotoBatchItem
from . import photo_batch_intake
from .photo_batch_intake import display_name, plan_uploads
from .photo_names import HolderIndex
from .storage import delete_quietly, put_bytes, signed_url
from .switches import cutout_on

LIFETIME = timedelta(days=7)
MAX_OPEN_BATCHES = 5
ATTACH = (CardPhotoBatchItem.Decision.APPLY, CardPhotoBatchItem.Decision.REPLACE)


def eraser_available(space, kind):
    return cutout_on(space, kind) and provider.configured(space)


def get_batch(actor, space_id, batch_id):
    """The batch, after the actor's authority for ITS kind is re-checked (404 across tenants)."""
    batch = CardPhotoBatch.objects.filter(pk=batch_id, makerspace_id=space_id).first()
    if batch is None:
        raise NotFound()
    space, event = roster.authorise(actor, batch.kind, space_id, batch.event_id)
    return batch, space, event


@transaction.atomic
def create(actor, space, kind, event, *, holders_consented, remove_backgrounds):
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    assert_write_allowed(space.pk)
    if not holders_consented:
        raise ValidationError({"holders_consented": gettext("Confirm the people in these photos agreed to them being stored and printed.")})
    if remove_backgrounds and not eraser_available(space, kind):
        raise ValidationError({"remove_backgrounds": gettext("Background removal is not set up for this space.")})
    from apps.makerspaces.models import Makerspace
    Makerspace.objects.select_for_update().only("pk").get(pk=space.pk)  # L-M2: count open batches one creator at a time
    if CardPhotoBatch.objects.filter(makerspace=space, state=CardPhotoBatch.State.DRAFT).count() >= MAX_OPEN_BATCHES:
        raise ValidationError({"detail": gettext("Finish or cancel an open photo batch first.")})
    now = timezone.now()
    batch = CardPhotoBatch.objects.create(makerspace=space, kind=kind, event_id=event.pk if event else None,
                                          created_by=actor, remove_backgrounds=remove_backgrounds,
                                          holders_consented=True, expires_at=now + LIFETIME)
    audit.record(actor, "card_photo_batch.created", makerspace=space, target=batch,
                 meta={"batch_id": batch.pk, "holder_kind": kind, "event_id": batch.event_id,
                       "holders_consented": True, "remove_backgrounds": remove_backgrounds})
    return batch


def _key(batch):
    return f"card-photo-batches/{batch.makerspace_id}/{batch.pk}/{uuid.uuid4().hex}"


def add_files(batch, space, event, uploads):
    """Store, validate and match the uploaded photos. -> number of non-image files skipped.

    One photo at a time (M11): read, re-encode, store, drop the bytes, so a request holds one photo in memory,
    never the whole upload. Every guard that needs no bytes ran in `plan_uploads` first; a refusal found while
    reading (a lying zip header, an archive behind an image name) deletes what this request already stored.
    """
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    assert_write_allowed(space.pk)
    if batch.state != CardPhotoBatch.State.DRAFT or batch.expires_at <= timezone.now():
        raise ValidationError({"detail": gettext("This batch is no longer open.")})
    intake = plan_uploads(uploads, existing=batch.file_count)
    people = roster.holders(batch, space, event)
    index, by_id = HolderIndex(people), {person["id"]: person for person in people}
    taken = set(batch.items.exclude(holder_id=None).values_list("holder_id", flat=True))
    position = (batch.items.order_by("-position").values_list("position", flat=True).first() or 0) + 1
    rows, written = [], []
    try:
        for name, load in intake.photos:
            row = CardPhotoBatchItem(batch=batch, position=position, filename=display_name(name))
            position += 1
            try:
                png = normalise(load(), max_edge=1200, keep_alpha=False)[0]
            except ValidationError as refused:
                if "files" in getattr(refused, "detail", {}):  # an intake guard, not an unreadable photo
                    raise
                row.state, row.error_code, row.decision = "failed", "unreadable_image", "skip"
                rows.append(row)
                continue
            row.file_key, row.size_bytes = _key(batch), len(png)
            put_bytes(row.file_key, png, "image/png")
            written.append(row.file_key)
            del png
            _match(row, index, by_id, taken, name)
            rows.append(row)
        with transaction.atomic():
            # L-M2: two uploads to one batch both passed the cap on the count they read; re-check under the lock.
            locked = CardPhotoBatch.objects.select_for_update().get(pk=batch.pk)
            if locked.state != CardPhotoBatch.State.DRAFT:
                raise ValidationError({"detail": gettext("This batch is no longer open.")})
            cap = photo_batch_intake.MAX_FILES
            if locked.items.count() + len(rows) > cap:
                raise ValidationError({"files": gettext("A batch holds at most %(n)d photos.") % {"n": cap}})
            CardPhotoBatchItem.objects.bulk_create(rows)
            CardPhotoBatch.objects.filter(pk=batch.pk).update(file_count=batch.items.count())
    except Exception:
        for key in written:
            delete_quietly(key)
        raise
    finally:
        intake.close()
    batch.refresh_from_db()
    return intake.skipped


def _match(row, index, by_id, taken, name):
    row.match_kind, row.candidates = index.match(name)
    if len(row.candidates) == 1:
        holder = row.candidates[0]
        row.holder_id, row.has_photo = holder, by_id[holder]["has_photo"]
        if holder in taken:  # a second photo for one holder: the first wins, the extra is skipped
            row.decision, row.error_code = "skip", "duplicate_file"
        else:
            taken.add(holder)
            row.decision = "keep" if row.has_photo else "apply"
    else:
        row.decision = "skip"


def _status(item):
    if item.error_code == "unreadable_image" or (not item.holder_id and len(item.candidates) <= 1):
        return "unmatched"
    if not item.holder_id:
        return "ambiguous"
    return "has_photo" if item.has_photo else "matched"


def review(batch, space, event):
    people = roster.holders(batch, space, event)
    by_id = {person["id"]: person for person in people}
    short = lambda p: {"id": p["id"], "name": p["name"], "number": p["number"]}  # noqa: E731
    items = []
    for item in batch.items.all():
        try:
            url = signed_url(item.file_key) if item.file_key else ""
        except Exception:
            url = ""
        holder = by_id.get(item.holder_id)
        items.append({"id": item.pk, "filename": item.filename, "status": _status(item), "match_kind": item.match_kind,
                      "holder_id": item.holder_id, "holder_name": holder["name"] if holder else "",
                      "candidates": [short(by_id[c]) for c in item.candidates if c in by_id],
                      "decision": item.decision, "state": item.state, "error_code": item.error_code,
                      "thumbnail_url": url})
    return {"id": batch.pk, "kind": batch.kind, "event_id": batch.event_id, "state": batch.state,
            "remove_backgrounds": batch.remove_backgrounds, "eraser_available": eraser_available(space, batch.kind),
            "file_count": batch.file_count, "applied_count": batch.applied_count,
            "skipped_count": batch.skipped_count, "failed_count": batch.failed_count, "expires_at": batch.expires_at,
            "items": items, "holders": [short(p) for p in people]}


def choose(batch, space, event, item_id, *, holder_id=None, decision=None, set_holder=False):
    """Pick the holder for an ambiguous or unmatched file, and/or replace / keep / skip. `set_holder` False = unchanged."""
    if batch.state != CardPhotoBatch.State.DRAFT:
        raise ValidationError({"detail": gettext("This batch is no longer open.")})
    item = batch.items.filter(pk=item_id).first()
    if item is None:
        raise NotFound()
    if set_holder:
        if holder_id is None:
            item.holder_id, item.has_photo, item.decision = None, False, "skip"
        else:
            person = next((p for p in roster.holders(batch, space, event) if p["id"] == holder_id), None)
            if person is None:
                raise ValidationError({"holder_id": gettext("That person is not part of this batch's cards.")})
            if batch.items.exclude(pk=item.pk).filter(holder_id=holder_id).exists():
                raise ValidationError({"holder_id": gettext("Another photo is already chosen for that person.")})
            item.holder_id, item.has_photo, item.match_kind = holder_id, person["has_photo"], "manual"
            item.decision = "keep" if person["has_photo"] else "apply"
            item.error_code = "" if item.error_code == "duplicate_file" else item.error_code
    if decision:
        if decision in ("apply", "replace"):
            if not item.holder_id or item.state == "failed":
                raise ValidationError({"decision": gettext("Choose a person first.")})
            decision = "replace" if item.has_photo else "apply"
        item.decision = decision
    item.save()
    return item


def apply(actor, batch, space, remove_backgrounds=None):
    """Start applying: only the chosen, matched photos are attached (through the normal photo path)."""
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    assert_write_allowed(space.pk)
    with transaction.atomic():
        batch = CardPhotoBatch.objects.select_for_update().get(pk=batch.pk)
        if batch.state != CardPhotoBatch.State.DRAFT:
            raise ValidationError({"detail": gettext("This batch is no longer open.")})
        count = batch.items.filter(state="pending", decision__in=ATTACH).exclude(holder_id=None).count()
        if not count:
            raise ValidationError({"detail": gettext("No photo is chosen to apply.")})
        if remove_backgrounds is not None:
            batch.remove_backgrounds = remove_backgrounds
        if batch.remove_backgrounds and not eraser_available(space, batch.kind):
            raise ValidationError({"remove_backgrounds": gettext("Background removal is not set up for this space.")})
        batch.state = CardPhotoBatch.State.APPLYING
        batch.save(update_fields=["state", "remove_backgrounds"])
        audit.record(actor, "card_photo_batch.applied", makerspace=space, target=batch,
                     meta={"batch_id": batch.pk, "holder_kind": batch.kind, "count": count})
        from .tasks import process_photo_batch
        transaction.on_commit(lambda: process_photo_batch.delay(batch.pk))
    return batch


def cancel(actor, batch, space):
    if batch.state != CardPhotoBatch.State.DRAFT:
        raise ValidationError({"detail": gettext("This batch is no longer open.")})
    _drop_objects(batch)
    batch.state = CardPhotoBatch.State.CANCELLED
    batch.save(update_fields=["state"])
    audit.record(actor, "card_photo_batch.cancelled", makerspace=space, target=batch,
                 meta={"batch_id": batch.pk, "holder_kind": batch.kind})


def release_item_file(instance, **_kwargs):
    """post_delete on CardPhotoBatchItem: a batch removed by a space purge must not leave its photos behind."""
    if instance.file_key:
        transaction.on_commit(lambda: delete_quietly(instance.file_key))


def _drop_objects(batch):
    for item in batch.items.exclude(file_key=""):
        delete_quietly(item.file_key)
    batch.items.exclude(file_key="").update(file_key="")


def purge_expired_batches(limit=50):
    """Photos of an abandoned batch are temporary: gone 7 days after creation, finished or not."""
    now = timezone.now()
    for batch in CardPhotoBatch.objects.filter(expires_at__lte=now).exclude(
            state=CardPhotoBatch.State.APPLYING).filter(items__file_key__gt="").distinct()[:limit]:
        _drop_objects(batch)
        if batch.state == CardPhotoBatch.State.DRAFT:
            CardPhotoBatch.objects.filter(pk=batch.pk).update(state=CardPhotoBatch.State.CANCELLED)
    return 0
