"""Card-photo cut-outs (decision 314(c)): queue, run, choose, discard, purge and the card-engine resolver.
The original photo is never changed. A cut-out is a DERIVED private object (`card-cutouts/<space>/<uuid>`) linked to
the holder's card, valid only while made from the card's current photo (`source_key`); a staff card's request is stored
against the member card whose photo it shows. Switch off = 404; the limit `photo_cutout_jobs_monthly` refuses only the
START of a new job; an opted-out member (`eraser_notice`) is never sent. Changes are audited by id and code only."""
import logging
import uuid
from io import BytesIO

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext
from rest_framework.exceptions import NotFound, ValidationError

from apps.audit import services as audit

from .holders import spec_for
from .image_adapter import client, provider
from .image_adapter.contract import INPUT_TYPES
from .image_adapter.errors import AdapterError
from .models_cutout import CardPhotoCutout
from .storage import delete_quietly, put_bytes, signed_url
from .switches import cutout_on

logger = logging.getLogger(__name__)
LIMIT_KEY = "photo_cutout_jobs_monthly"  # decision 284: default none, refuses only a new job
MAX_ATTEMPTS = 4
BACKOFF_SECONDS = (30, 120, 600)
STALE_AFTER_SECONDS = 15 * 60  # a running row nobody finished (worker died) is picked up again


def owner(kind, card):
    """-> (kind, card) whose photo this holder shows, or None. A staff card shows its member card's photo."""
    if kind != "staff_card":
        return kind, card
    from apps.makerspaces.models import MemberCard
    member = MemberCard.objects.filter(membership_id=card.membership_id, makerspace_id=card.makerspace_id,
                                       revoked_at__isnull=True).exclude(photo_object_key="").first()
    return ("member_card", member) if member else None


def _current_key(kind, card):
    return getattr(card, "photo_object_key", "") or ""


def row_for(kind, card):
    return CardPhotoCutout.objects.filter(**{kind: card}).first()


def _state(row, kind, card):
    if row is None:
        return "none"
    if row.source_key != _current_key(kind, card):
        return "stale"
    return row.state


def status(kind, card, *, space=None):
    """The shape the UI reads: availability, state, choice and a short-lived private image link."""
    space = space or card.makerspace
    own = owner(kind, card)
    row = row_for(*own) if own else None
    state = _state(row, *own) if own else "none"
    url = ""
    if state == "done" and row.cutout_key:
        try:
            url = signed_url(row.cutout_key)
        except Exception:
            logger.warning("cutout_link_unavailable")
    return {"available": bool(own) and cutout_on(space, kind) and provider.configured(space), "state": state,
            "error_code": row.error_code if row and state in ("failed", "queued") else "",
            "use": "cutout" if row and state == "done" and row.use_cutout else "original", "image_url": url,
            "width": row.width if row and state == "done" else 0, "height": row.height if row and state == "done" else 0,
            "requested_at": row.created_at if row else None}


def _require_on(space, kind):
    if not cutout_on(space, kind):
        raise NotFound()


def _audit(actor, action, row, kind, extra=None):
    audit.record(actor, action, makerspace=row.makerspace, target=row,
                 meta={"card_id": row.holder_id, "holder_kind": kind, "cutout_id": row.pk, **(extra or {})})


@transaction.atomic
def request(actor, kind, card, *, by_holder=False, consent=False):
    """Queue a background removal for the holder's current photo. Returns the (possibly already queued) row."""
    from apps.managed_hosting.extra_quotas import check_extra_quota_locked
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    space = card.makerspace
    assert_write_allowed(space.pk)
    _require_on(space, kind)
    own = owner(kind, card)
    if own is None or not _current_key(*own):
        raise ValidationError({"detail": gettext("Add a photo first.")})
    if not provider.configured(space):
        raise ValidationError({"detail": gettext("No eraser service is set up for this space."),
                               "code": "eraser_not_configured"})
    if by_holder and not consent:
        raise ValidationError({"consent": gettext("Agree to your photo being sent to the eraser service first.")})
    okind, ocard = own
    from .eraser_notice import NOTICE_VERSION, refuse_if_opted_out
    refuse_if_opted_out(okind, ocard)  # decision 345(b): an opted-out member's photo is never sent, by anyone
    type(ocard).objects.select_for_update().filter(pk=ocard.pk).first()  # L-M2: one request per card at a time
    existing = row_for(okind, ocard)
    if existing and existing.source_key == _current_key(okind, ocard) and existing.state in ("queued", "running"):
        return existing
    check_extra_quota_locked(space, LIMIT_KEY)
    if existing:
        purge_row(existing)
    row = CardPhotoCutout.objects.create(makerspace=ocard.makerspace, requested_by=actor, by_holder=by_holder,
                                         consent_at=timezone.now() if by_holder else None, notice_version=NOTICE_VERSION,
                                         source_key=_current_key(okind, ocard), **{okind: ocard})
    _audit(actor, "card.photo_cutout_requested", row, okind, {"by_holder": by_holder})
    from .tasks import dispatch_cutout
    transaction.on_commit(lambda: dispatch_cutout(row.pk))
    return row


def _claim(cutout_id):
    """Take a queued (or abandoned running) row for one attempt; None when there is nothing to do."""
    from datetime import timedelta
    with transaction.atomic():
        row = CardPhotoCutout.objects.select_for_update().filter(pk=cutout_id).first()
        if row is None:
            return None
        abandoned = row.state == "running" and row.updated_at < timezone.now() - timedelta(seconds=STALE_AFTER_SECONDS)
        if row.state != "queued" and not abandoned:
            return None
        if abandoned and row.attempts >= MAX_ATTEMPTS:  # a worker died (hard time limit) on every try: stop here
            _fail(row, "provider_timeout")
            return None
        row.state, row.attempts = CardPhotoCutout.State.RUNNING, row.attempts + 1
        row.save(update_fields=["state", "attempts", "updated_at"])
        return row


def _fail(row, code):
    row.state, row.error_code, row.finished_at = CardPhotoCutout.State.FAILED, code, timezone.now()
    row.save(update_fields=["state", "error_code", "finished_at", "updated_at"])
    _audit(row.requested_by, "card.photo_cutout_failed", row, row.holder_kind, {"error_code": code})


def _mime(data):
    from PIL import Image
    try:
        with Image.open(BytesIO(data)) as image:
            mime = Image.MIME.get(image.format, "")
    except Exception:
        return ""
    return mime if mime in INPUT_TYPES else ""


def timed_out(cutout_id):
    """The attempt hit the task's soft time limit: requeue with backoff like a provider timeout, or give up."""
    row = CardPhotoCutout.objects.filter(pk=cutout_id, state=CardPhotoCutout.State.RUNNING).first()
    if row is None:
        return None
    if row.attempts < MAX_ATTEMPTS:
        CardPhotoCutout.objects.filter(pk=row.pk).update(state="queued", error_code="provider_timeout")
        return BACKOFF_SECONDS[min(row.attempts - 1, len(BACKOFF_SECONDS) - 1)]
    return _fail(row, "provider_timeout")


def run(cutout_id):
    """One attempt. -> seconds to wait before the next attempt, or None when finished (done or failed)."""
    from apps.makerspaces.limits_usage import add_storage, free_storage
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    row = _claim(cutout_id)
    if row is None:
        return None
    kind = row.holder_kind
    card = getattr(row, kind)
    space = row.makerspace
    assert_write_allowed(space.pk)
    if not cutout_on(space, kind):
        return _fail(row, "not_configured")
    data = spec_for(kind).photo_bytes(card) if row.source_key == _current_key(kind, card) else None
    config = provider.resolve(space)
    if not data or config is None or not _mime(data):
        return _fail(row, "photo_missing" if not data else ("not_configured" if config is None else "input_not_allowed"))
    try:
        png, width, height = client.remove_background(config, data, _mime(data))
    except AdapterError as exc:
        if exc.retryable and row.attempts < MAX_ATTEMPTS:
            CardPhotoCutout.objects.filter(pk=row.pk).update(state="queued", error_code=exc.code)
            return BACKOFF_SECONDS[min(row.attempts - 1, len(BACKOFF_SECONDS) - 1)]
        return _fail(row, exc.code)
    key = f"card-cutouts/{space.pk}/{uuid.uuid4().hex}"
    charged = False  # M10: free only what was charged (a refusal at the cap charged nothing)
    try:
        add_storage(space, len(png))
        charged = True
        put_bytes(key, png, "image/png")
    except Exception:
        if charged:
            free_storage(space, len(png))
            delete_quietly(key)
        logger.warning("cutout_store_failed")
        return _fail(row, "storage_unavailable")
    with transaction.atomic():
        fresh = CardPhotoCutout.objects.select_for_update().filter(pk=row.pk).first()
        card = getattr(fresh, kind) if fresh else None
        if fresh is None or card is None or fresh.source_key != _current_key(kind, card):
            transaction.on_commit(lambda: (delete_quietly(key), free_storage(space, len(png))))
            return None
        fresh.state, fresh.cutout_key, fresh.content_type = CardPhotoCutout.State.DONE, key, "image/png"
        fresh.size_bytes, fresh.width, fresh.height = len(png), width, height
        fresh.provider_scope, fresh.error_code, fresh.finished_at = config.scope, "", timezone.now()
        fresh.save()
        _audit(fresh.requested_by, "card.photo_cutout_done", fresh, kind, {"provider_scope": config.scope})
    return None


def set_use(actor, kind, card, use):
    """"Use cut-out" or "Use original": which one the card's photo layer shows by default."""
    space = card.makerspace
    _require_on(space, kind)
    own = owner(kind, card)
    row = row_for(*own) if own else None
    if row is None or _state(row, *own) != "done":
        raise ValidationError({"detail": gettext("There is no cut-out ready to use.")})
    row.use_cutout = use == "cutout"
    row.save(update_fields=["use_cutout", "updated_at"])
    _audit(actor, "card.photo_cutout_choice", row, own[0], {"use": use})
    return row


def discard(actor, kind, card):
    """Remove the cut-out (object and row); the original photo is untouched."""
    own = owner(kind, card)
    row = row_for(*own) if own else None
    if row is None:
        raise NotFound()
    _audit(actor, "card.photo_cutout_discarded", row, own[0])
    purge_row(row)


def purge_row(row):
    """Delete the row; the post_delete hook deletes the derived object and gives the storage back."""
    row.delete()


def purge_for_card(kind, card):
    """The original photo was removed: its cut-out must not outlive it (a replaced photo makes it stale instead)."""
    own = owner(kind, card)
    row = row_for(*own) if own else None
    if row is not None:
        purge_row(row)


def release_deleted(instance, **_kwargs):
    """post_delete on CardPhotoCutout (also fires on card, account and tenant purge cascades)."""
    from apps.makerspaces.limits_usage import free_storage
    key, size, space_id = instance.cutout_key, instance.size_bytes, instance.makerspace_id
    if not key:
        return

    def _release():
        from apps.makerspaces.models import Makerspace
        delete_quietly(key)
        space = Makerspace.objects.filter(pk=space_id).first()
        if space is not None:
            free_storage(space, size)
    transaction.on_commit(_release)


def photo_variant_bytes(kind, card, variant="auto"):
    """The card engine's photo resolver. `variant` is the photo layer's `variant`: "original" (-> None, use the
    normal photo), "cutout" (the cut-out when one is ready for the current photo) or "auto" (the cut-out only when
    the holder or staff chose "Use cut-out"). Returns PNG bytes with alpha, or None to fall back to the original.
    Bytes are read from private storage on the server; the cut-out is never given a public URL."""
    if variant == "original":
        return None
    own = owner(kind, card)
    row = row_for(*own) if own else None
    if row is None or _state(row, *own) != "done" or (variant == "auto" and not row.use_cutout):
        return None
    if not cutout_on(row.makerspace, own[0]):
        return None
    from .storage import read_optional
    return read_optional(row.cutout_key)


def resume_stuck(limit=50):
    """Sweep for broker loss: re-dispatch queued rows nobody is working and abandoned running ones."""
    from datetime import timedelta
    from django.db.models import Q
    from .tasks import dispatch_cutout
    cutoff = timezone.now() - timedelta(seconds=STALE_AFTER_SECONDS)
    ids = list(CardPhotoCutout.objects.filter(Q(state="queued", updated_at__lte=cutoff)
                                              | Q(state="running", updated_at__lte=cutoff)).values_list(
        "pk", flat=True)[:limit])
    for cutout_id in ids:
        dispatch_cutout(cutout_id)
    return len(ids)
