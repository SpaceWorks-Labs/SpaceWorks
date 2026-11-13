"""Holder photos for programme and event cards, and the "photo needs update" request.

Member-card photos keep their existing flow (`makerspaces.member_card_storage`). Here:
the browser gets a presign for `staging/<final>` only; finalising reads the staged
bytes, sniffs and re-encodes them (metadata stripped, <= 1200 px), writes the final
key server-side, charges storage and records consent (Hard Rule: staging -> final).
"""
from django.utils.translation import gettext
import uuid
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit

from .images import MAX_UPLOAD_BYTES, normalise
from .models import CardPhotoRequest
from .storage import delete_quietly, presign_staging, put_bytes, take_staging

CONSENT_VERSION = "2026-11"
REMINDER_AFTER = timedelta(days=7)


def final_key(card):
    return f"card-photos/{card.makerspace_id}/{uuid.uuid4().hex}"


def _valid_key(card, key):
    prefix = f"card-photos/{card.makerspace_id}/"
    if not isinstance(key, str) or not key.startswith(prefix) or "/" in key[len(prefix):]:
        raise ValidationError({"object_key": gettext("Unknown upload.")})


def presign(card, content_type):
    from .images import ALLOWED
    if content_type not in ALLOWED:
        raise ValidationError({"content_type": gettext("Upload a PNG, JPEG or WebP photo.")})
    key = final_key(card)
    return {"object_key": key, "content_type": content_type, **presign_staging(key, content_type, MAX_UPLOAD_BYTES)}


def attach_bytes(actor, kind, card, data, *, consent):
    """Store already-validated bytes as the card's photo; frees the old object."""
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    assert_write_allowed(card.makerspace_id)
    from apps.makerspaces.limits_usage import add_storage, free_storage
    if not consent:
        raise ValidationError({"consent": gettext("A photo needs the holder's consent to be stored.")})
    png, _w, _h, _mean = normalise(data, max_edge=1200, keep_alpha=False)
    key = final_key(card)
    with transaction.atomic():
        row = type(card).objects.select_for_update().get(pk=card.pk)
        old_key, old_size = row.photo_object_key, row.photo_size_bytes or 0
        # Charge first: a space at its storage cap is refused before any bytes reach the bucket (no orphan object).
        add_storage(row.makerspace, len(png))
        put_bytes(key, png, "image/png")
        transaction.on_commit(lambda: _purge_stale_cutout(kind, row))
        row.photo_object_key, row.photo_content_type, row.photo_size_bytes = key, "image/png", len(png)
        row.photo_consent_at, row.photo_consent_version = timezone.now(), CONSENT_VERSION
        row.save(update_fields=["photo_object_key", "photo_content_type", "photo_size_bytes", "photo_consent_at",
                                "photo_consent_version", "updated_at"])
        resolve_requests(kind, row)
        if kind == "programme_card":
            audit.record(actor, "id_programme.card_photo_updated", makerspace=row.makerspace, target=row,
                         meta={"card_id": row.pk})
        else:
            audit.record(actor, "event_card.photo_updated", makerspace=row.makerspace, target=row,
                         meta={"card_id": row.pk})
        if old_key:
            transaction.on_commit(lambda: (delete_quietly(old_key), free_storage(row.makerspace, old_size)))
    return row


def _purge_stale_cutout(kind, card):
    """A replaced photo leaves its cut-out stale (never printed); delete it so its storage charge goes back too."""
    from .cutout_staleness import purge_if_stale
    purge_if_stale(kind, card)


def finalize(actor, kind, card, *, object_key, consent):
    _valid_key(card, object_key)
    data = take_staging(object_key, MAX_UPLOAD_BYTES)
    if data is None:
        raise ValidationError({"object_key": gettext("Upload not found; upload the photo first.")})
    return attach_bytes(actor, kind, card, data, consent=consent)


def remove(actor, kind, card):
    from apps.makerspaces.limits_usage import free_storage
    if not card.photo_object_key:
        return card
    key, size = card.photo_object_key, card.photo_size_bytes or 0
    card.photo_object_key, card.photo_content_type, card.photo_size_bytes = "", "", None
    card.photo_consent_at, card.photo_consent_version = None, ""
    card.save(update_fields=["photo_object_key", "photo_content_type", "photo_size_bytes", "photo_consent_at",
                             "photo_consent_version", "updated_at"])
    from .cutouts import purge_for_card
    purge_for_card(kind, card)  # D314c: the derived cut-out goes with its original
    delete_quietly(key)
    free_storage(card.makerspace, size)
    if kind == "programme_card":
        audit.record(actor, "id_programme.card_photo_removed", makerspace=card.makerspace, target=card,
                     meta={"card_id": card.pk})
    else:
        audit.record(actor, "event_card.photo_removed", makerspace=card.makerspace, target=card,
                     meta={"card_id": card.pk})
    return card


def photo_bytes(card):
    from .storage import read_optional
    return read_optional(getattr(card, "photo_object_key", ""), MAX_UPLOAD_BYTES)


@transaction.atomic
def request_update(actor, kind, card, reason):
    """Q-I4: the card stays valid; the holder is told now and reminded once after 7 days."""
    row = CardPhotoRequest.objects.filter(**{kind: card}, resolved_at__isnull=True).first()
    if row is None:
        row = CardPhotoRequest.objects.create(makerspace_id=card.makerspace_id, requested_by=actor,
                                              reason=(reason or "")[:300], **{kind: card})
    audit.record(actor, "card.photo_requested", makerspace=card.makerspace, target=card,
                 meta={"card_id": card.pk, "holder_kind": kind, "request_id": row.pk})
    from .notifications import photo_requested
    transaction.on_commit(lambda: photo_requested(row.pk), robust=True)
    return row


def resolve_requests(kind, card):
    CardPhotoRequest.objects.filter(**{kind: card}, resolved_at__isnull=True).update(resolved_at=timezone.now())


def send_due_reminders(*, limit=200):
    from .notifications import photo_requested
    from .switches import live_holder_q
    # Only card kinds switched on for their space (#183B); an off kind keeps its request.
    due = CardPhotoRequest.objects.filter(live_holder_q(), resolved_at__isnull=True, reminded_at__isnull=True,
                                          created_at__lte=timezone.now() - REMINDER_AFTER).order_by("pk")[:limit]
    sent = 0
    for row in due:
        CardPhotoRequest.objects.filter(pk=row.pk).update(reminded_at=timezone.now())
        photo_requested(row.pk, reminder=True)
        sent += 1
    return sent
