"""Minimized, import-remappable equipment proposal intents."""
import hashlib
import json
import re
from uuid import UUID
from django.core.exceptions import ValidationError
from django.utils.translation import gettext

KEYS = frozenset({"version", "makerspace_id", "operation_id", "original_borrower_id",
                  "original_creator_id", "intent_kind", "outcome_kind", "event_registration_id",
                  "booking_id", "waitlist_entry_id", "product_ids", "kit", "content_sha256"})


def _id(value, nullable=False):
    if value is None and nullable:
        return None
    if type(value) is not int or not 0 < value <= 9007199254740991:
        raise ValidationError(gettext("Invalid proposal."))
    return value


def _json(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValidationError(gettext("Invalid proposal.")) from exc


def canonical_intent_json(snapshot):
    if not isinstance(snapshot, dict) or set(snapshot) != KEYS or type(snapshot["version"]) is not int or snapshot["version"] != 2:
        raise ValidationError(gettext("Invalid proposal."))
    for key in ("makerspace_id", "original_borrower_id", "original_creator_id"):
        _id(snapshot[key])
    for key in ("event_registration_id", "booking_id", "waitlist_entry_id"):
        _id(snapshot[key], nullable=True)
    try:
        if str(UUID(snapshot["operation_id"])) != snapshot["operation_id"]:
            raise ValueError
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValidationError(gettext("Invalid proposal.")) from exc
    if (not isinstance(snapshot["intent_kind"], str) or snapshot["intent_kind"] not in {"self", "staff"}
            or not isinstance(snapshot["outcome_kind"], str) or snapshot["outcome_kind"] not in {"request", "consumable_plan"}):
        raise ValidationError(gettext("Invalid proposal."))
    ids, kit = snapshot["product_ids"], snapshot["kit"]
    if (ids is None) == (kit is None):
        raise ValidationError(gettext("Invalid proposal."))
    if ids is not None:
        if not isinstance(ids, list) or not 1 <= len(ids) <= 20 or len({_id(item) for item in ids}) != len(ids):
            raise ValidationError(gettext("Invalid proposal."))
    if kit is not None:
        if not isinstance(kit, dict) or set(kit) != {"id", "version"}:
            raise ValidationError(gettext("Invalid proposal."))
        _id(kit["id"])
        _id(kit["version"])
    if not isinstance(snapshot["content_sha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", snapshot["content_sha256"]):
        raise ValidationError(gettext("Invalid proposal."))
    text = _json(snapshot)
    if len(text) > 16384:
        raise ValidationError(gettext("Invalid proposal."))
    return text


def make_proposal_intent(*, makerspace_id, operation_id, original_borrower_id, original_creator_id,
                         intent_kind, outcome_kind, event_registration_id, booking_id, request_fields):
    if not isinstance(request_fields, dict):
        raise ValidationError(gettext("Invalid proposal."))
    allowed = {"items", "kit", "requested_for", "pickup_from", "pickup_until", "waitlist_entry_id"}
    if not set(request_fields) <= allowed or ("items" in request_fields) == ("kit" in request_fields):
        raise ValidationError(gettext("Invalid proposal."))
    items = request_fields.get("items")
    quantities = product_ids = None
    if items is not None:
        if not isinstance(items, list) or not 1 <= len(items) <= 20:
            raise ValidationError(gettext("Invalid proposal."))
        product_ids, quantities = [], []
        for item in items:
            if not isinstance(item, dict) or set(item) != {"product_id", "quantity"}:
                raise ValidationError(gettext("Invalid proposal."))
            product_ids.append(_id(item["product_id"]))
            quantity = item["quantity"]
            if type(quantity) is not int or not 1 <= quantity <= 99:
                raise ValidationError(gettext("Invalid proposal."))
            quantities.append(quantity)
    purpose = request_fields.get("requested_for", "")
    if not isinstance(purpose, str) or len(purpose) > 500:
        raise ValidationError(gettext("Invalid proposal."))
    content = {"requested_for": purpose, "pickup_from": request_fields.get("pickup_from"),
               "pickup_until": request_fields.get("pickup_until"), "quantities": quantities}
    for key in ("pickup_from", "pickup_until"):
        if content[key] is not None and (not isinstance(content[key], str) or len(content[key]) > 40):
            raise ValidationError(gettext("Invalid proposal."))
    content_hash = hashlib.sha256(b"spaceworks.equipment-proposal-content.v2\0" + _json(content).encode("ascii")).hexdigest()
    snapshot = {"version": 2, "makerspace_id": makerspace_id, "operation_id": str(operation_id),
                "original_borrower_id": original_borrower_id, "original_creator_id": original_creator_id,
                "intent_kind": intent_kind, "outcome_kind": outcome_kind,
                "event_registration_id": event_registration_id, "booking_id": booking_id,
                "waitlist_entry_id": request_fields.get("waitlist_entry_id"),
                "product_ids": product_ids, "kit": request_fields.get("kit"), "content_sha256": content_hash}
    canonical_intent_json(snapshot)
    return snapshot


def proposal_fingerprint_from_snapshot(snapshot):
    raw = canonical_intent_json(snapshot).encode("ascii")
    return hashlib.sha256(b"spaceworks.equipment-proposal.v2\0" + raw).hexdigest()
