"""Minimized versioned use intent; stock is owned by InventoryAdjustment."""
import hashlib
import json
import re
from uuid import UUID
from django.core.exceptions import ValidationError
from django.utils.translation import gettext

KEYS = frozenset({"version", "makerspace_id", "operation_id", "original_creator_id",
                  "product_id", "source_kind", "source_id", "content_sha256"})


def _json(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValidationError(gettext("Invalid consumable operation.")) from exc


def canonical_use_intent_json(snapshot):
    if not isinstance(snapshot, dict) or set(snapshot) != KEYS or type(snapshot["version"]) is not int or snapshot["version"] != 2:
        raise ValidationError(gettext("Invalid consumable operation."))
    for key in ("makerspace_id", "original_creator_id", "product_id", "source_id"):
        if type(snapshot[key]) is not int or not 0 < snapshot[key] <= 9007199254740991:
            raise ValidationError(gettext("Invalid consumable operation."))
    if not isinstance(snapshot["source_kind"], str) or snapshot["source_kind"] not in {"allocation", "plan"}:
        raise ValidationError(gettext("Invalid consumable operation."))
    try:
        if str(UUID(snapshot["operation_id"])) != snapshot["operation_id"]:
            raise ValueError
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValidationError(gettext("Invalid consumable operation.")) from exc
    if not isinstance(snapshot["content_sha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", snapshot["content_sha256"]):
        raise ValidationError(gettext("Invalid consumable operation."))
    result = _json(snapshot)
    if len(result) > 4096:
        raise ValidationError(gettext("Invalid consumable operation."))
    return result


def make_use_intent(*, makerspace_id, operation_id, original_creator_id, product_id, source_kind, source_id, quantity, note):
    if type(quantity) is not int or not 1 <= quantity <= 100000 or not isinstance(note, str) or len(note) > 200:
        raise ValidationError(gettext("Invalid consumable operation."))
    content = {"quantity": quantity, "note": note}
    content_hash = hashlib.sha256(b"spaceworks.equipment-use-content.v2\0" + _json(content).encode("ascii")).hexdigest()
    result = {"version": 2, "makerspace_id": makerspace_id, "operation_id": str(operation_id),
              "original_creator_id": original_creator_id, "product_id": product_id,
              "source_kind": source_kind, "source_id": source_id, "content_sha256": content_hash}
    canonical_use_intent_json(result)
    return result


def use_fingerprint_from_snapshot(snapshot):
    return hashlib.sha256(b"spaceworks.equipment-use.v2\0" + canonical_use_intent_json(snapshot).encode("ascii")).hexdigest()
