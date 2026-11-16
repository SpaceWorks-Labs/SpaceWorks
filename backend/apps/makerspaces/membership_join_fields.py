"""Parity O-B2: what a plan's join form collects besides its questions -- a photo, a phone number and a state.

Each plan chooses (`MembershipPlan.join_photo` off/optional/required, `join_phone` and `join_state`
hidden/optional/required); the switches `membership.join_photo` and `membership.join_contact_fields` turn the
whole thing off for a space (off = the form asks for nothing and the API refuses the keys).

The values are applicant data, so they ride inside the request's ALREADY-ENCRYPTED `application_answers`
snapshot under `join_fields` -- no new personal-data column. They reach the member only when the request activates:

* phone -> `User.phone`, only when the account has none (the verified `phone_e164` login identity is never touched);
* state -> `MembershipRecord.state_code` (the GST place of supply), only when the record has none;
* photo -> the member card photo, with the consent the applicant gave, only when the card has no photo
  (`apply_join_photo`, also called when a card is issued later). It never replaces an existing photo.
"""
import json
import logging
import re

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit
from apps.makerspaces.membership_admission_forms import encode_answers
from apps.makerspaces.membership_features import membership_feature_on

logger = logging.getLogger(__name__)
KEYS = {"phone", "state_code", "photo"}
_STATE = re.compile(r"^\d{2}$")
# (mode name, payload key, the "not collected" mode)
_FIELDS = (("photo", "photo", "off"), ("phone", "phone", "hidden"), ("state", "state_code", "hidden"))


def modes(space, plan):
    """The effective {photo, phone, state} modes: off / hidden when the plan or the switch says so."""
    if plan is None:
        return {"photo": "off", "phone": "hidden", "state": "hidden"}
    contact = membership_feature_on(space, "join_contact_fields")
    return {
        "photo": plan.join_photo if membership_feature_on(space, "join_photo") else "off",
        "phone": plan.join_phone if contact else "hidden",
        "state": plan.join_state if contact else "hidden",
    }


def _photo(space, raw):
    from apps.evidence import storage
    if not isinstance(raw, dict) or set(raw) - {"object_key", "content_type", "consent"}:
        raise ValidationError(gettext("Upload the photo first, then send its key and consent."))
    key, kind = str(raw.get("object_key") or ""), str(raw.get("content_type") or "")
    prefix = f"member-cards/{space.pk}/"
    if not key.startswith(prefix) or "/" in key[len(prefix):] or kind not in settings.EVIDENCE_ALLOWED_MIME:
        raise ValidationError(gettext("Unknown upload."))
    if raw.get("consent") is not True:
        raise ValidationError(gettext("A photo needs your consent to be stored."))
    if not storage.object_size(storage.staging_key(key)):
        raise ValidationError(gettext("Upload not found; upload the photo first."))
    return {"object_key": key, "content_type": kind, "consent_at": timezone.now().isoformat()}


def _one(space, key, value):
    if key == "photo":
        return _photo(space, value)
    if key == "phone":
        from apps.forms_schema.profile_fields import ProfileValueError, normalize_phone
        try:
            return normalize_phone(value)
        except ProfileValueError:
            raise ValidationError(gettext("Enter a valid phone number.")) from None
    if not isinstance(value, str) or not _STATE.match(value.strip()):
        raise ValidationError(gettext("Enter the two-digit state code, for example 29."))
    return value.strip()


def clean(space, plan, raw, *, existing=None):
    """Validated `join_fields` for a submission (None when nothing is collected).

    `existing` is the stored value on a resubmission: a required field already on file need not be sent again.
    """
    raw = raw if raw is not None else {}
    if not isinstance(raw, dict) or set(raw) - KEYS:
        raise ValidationError({"join_fields": gettext("Unknown join form fields.")})
    mode, existing, out, errors = modes(space, plan), existing or {}, {}, {}
    for name, key, off in _FIELDS:
        value = raw.get(key)
        if mode[name] == off:
            if value not in (None, "", {}):
                errors[key] = gettext("This plan does not ask for that.")
            continue
        if value in (None, "", {}):
            if existing.get(key):
                out[key] = existing[key]
            elif mode[name] == "required":
                errors[key] = gettext("This is required.")
            continue
        try:
            out[key] = _one(space, key, value)
        except ValidationError as exc:
            errors[key] = exc.detail
    if errors:
        raise ValidationError({"join_fields": errors})
    return out or None


def encode(schema, raw_answers, join_fields):
    """The stored snapshot: validated answers plus `join_fields` (a snapshot is created for a join form with no
    questions when there are extras to keep)."""
    encoded = encode_answers(schema, raw_answers)
    if not join_fields:
        return encoded
    snapshot = json.loads(encoded) if encoded else {"answers": []}
    snapshot["join_fields"] = join_fields
    return json.dumps(snapshot, ensure_ascii=False)


def stored(row):
    try:
        snapshot = json.loads(row.application_answers) if row.application_answers else {}
    except (ValueError, TypeError):
        return {}
    value = snapshot.get("join_fields") if isinstance(snapshot, dict) else None
    return value if isinstance(value, dict) else {}


def _save(row, join_fields):
    snapshot = json.loads(row.application_answers) if row.application_answers else {"answers": []}
    snapshot["join_fields"] = join_fields
    row.application_answers = json.dumps(snapshot, ensure_ascii=False)
    row.save(update_fields=["application_answers", "updated_at"])


def apply_on_activation(membership, request, actor=None):
    """Called inside the activation transaction. Never overwrites anything the account or staff already hold."""
    from apps.makerspaces.models import MembershipRecord
    values = stored(request) if request is not None else {}
    if not values:
        return []
    applied, user = [], membership.user
    if values.get("phone") and not user.phone:
        user.phone = values["phone"]
        user.save(update_fields=["phone"])
        applied.append("phone")
    if values.get("state_code"):
        record, _ = MembershipRecord.objects.get_or_create(
            membership=membership, defaults={"makerspace_id": membership.makerspace_id})
        if not record.state_code:
            record.state_code = values["state_code"]
            record.updated_by = actor
            record.save()
            applied.append("state_code")
    if applied:
        audit.record(actor, "membership.join_fields_applied", makerspace=membership.makerspace, target=membership,
                     meta={"fields": applied})
    if values.get("photo"):
        pk, makerspace_id = membership.pk, membership.makerspace_id
        transaction.on_commit(lambda: apply_join_photo_for_membership(pk, makerspace_id), robust=True)
    return applied


def apply_join_photo_for_membership(membership_id, makerspace_id):
    from apps.makerspaces.models import MemberCard
    card = MemberCard.objects.filter(membership_id=membership_id, makerspace_id=makerspace_id,
                                     revoked_at__isnull=True).select_related("membership", "makerspace").first()
    return apply_join_photo(card) if card is not None else False


def apply_join_photo(card):
    """Give a card the photo its owner attached to their join request. False when there was nothing to apply.

    Idempotent and never replaces a photo the card already has (the staged upload is dropped instead). A storage
    failure is logged and leaves the reference in place so a later card issue can retry.
    """
    from apps.evidence import storage
    from apps.makerspaces import member_card_storage
    from apps.makerspaces.models import MembershipRequest
    row = MembershipRequest.objects.filter(
        makerspace_id=card.makerspace_id, user_id=card.membership.user_id, state="active", admission_managed=True,
    ).order_by("-pk").first()
    values = stored(row) if row is not None else {}
    photo = values.get("photo")
    if not photo or photo.get("applied"):
        return False
    try:
        with transaction.atomic():
            if card.photo_object_key:
                storage.delete_object(storage.staging_key(photo["object_key"]))
            else:
                member_card_storage.finalize_photo(None, card, object_key=photo["object_key"],
                                                   content_type=photo["content_type"], consent=True)
            values["photo"] = {**photo, "applied": True}
            _save(row, values)
    except Exception:  # noqa: BLE001 -- a card photo must never undo an activation or a card issue
        logger.warning("membership_join_photo_failed", extra={"request_id": row.pk})
        return False
    return True


def presign_join_photo(space, plan, content_type):
    """A staging-only upload URL for the join-form photo (same bucket, MIME and size bounds as card photos)."""
    from apps.makerspaces import member_card_storage
    if modes(space, plan)["photo"] == "off":
        raise ValidationError({"detail": gettext("This plan does not ask for a photo.")})
    if content_type not in settings.EVIDENCE_ALLOWED_MIME:
        raise ValidationError({"content_type": gettext("Unsupported image type.")})
    from apps.evidence import storage
    final_key = member_card_storage._final_key(space.pk)
    return {"object_key": final_key, "content_type": content_type,
            **storage.presigned_upload(final_key, content_type)}
