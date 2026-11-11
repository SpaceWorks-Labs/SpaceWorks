"""Canonical encrypted intent for idempotent use of the existing stock ledger."""
import hashlib
import json
from uuid import UUID

from django.core.exceptions import ValidationError
from django.utils.translation import gettext

KEYS = frozenset({"version", "makerspace_id", "operation_id", "original_creator_id",
                  "product_id", "source_kind", "source_id", "quantity", "note"})
MAX_SAFE_ID = 9007199254740991


def canonical_use_intent_json(snapshot):
    if not isinstance(snapshot, dict) or set(snapshot) != KEYS or type(snapshot["version"]) is not int or snapshot["version"] != 1:
        raise ValidationError(gettext("Invalid consumable operation."))
    for key in ("makerspace_id", "original_creator_id", "product_id", "source_id"):
        value = snapshot[key]
        if type(value) is not int or not 0 < value <= MAX_SAFE_ID:
            raise ValidationError(gettext("Invalid consumable operation."))
    if (not isinstance(snapshot["source_kind"], str) or snapshot["source_kind"] not in {"allocation", "plan"} or type(snapshot["quantity"]) is not int
            or not 1 <= snapshot["quantity"] <= 100000 or not isinstance(snapshot["note"], str)
            or len(snapshot["note"]) > 200):
        raise ValidationError(gettext("Invalid consumable operation."))
    try:
        if str(UUID(snapshot["operation_id"])) != snapshot["operation_id"]:
            raise ValueError
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValidationError(gettext("Invalid consumable operation.")) from exc
    text = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    if len(text) > 4096:
        raise ValidationError(gettext("Invalid consumable operation."))
    return text


def use_fingerprint_from_snapshot(snapshot):
    raw = canonical_use_intent_json(snapshot).encode("ascii")
    return hashlib.sha256(b"spaceworks.equipment-consumable-use.v1\0" + raw).hexdigest()
