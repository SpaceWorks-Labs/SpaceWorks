"""Canonical core command encoding, independent of Django and domain runtime."""
from datetime import UTC, date, datetime
from decimal import Decimal
from hashlib import sha256
import json
from uuid import UUID

from .validation import closed, minor, reason_code, PayoutValidationError


def utc(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise PayoutValidationError("aware_datetime_required")
    value = value.astimezone(UTC)
    return value.isoformat(timespec="microseconds" if value.microsecond else "seconds").replace("+00:00", "Z")


def _default(value):
    if isinstance(value, datetime):
        return utc(value)
    if isinstance(value, (UUID, Decimal)):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError("Unsupported command value.")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False, default=_default)


def fingerprint(value):
    return sha256(canonical(value).encode("utf8")).hexdigest()


def cancellation_command(data):
    closed(data, ("operation_id", "expected_version", "expected_revision_sequence",
                  "expected_pool_version", "reason_code", "note"))
    try:
        operation = str(UUID(str(data["operation_id"])))
    except (ValueError, TypeError, AttributeError):
        raise PayoutValidationError("invalid_operation_id") from None
    for key in ("expected_version", "expected_revision_sequence"):
        minor(data[key], field=key)
    if data["expected_pool_version"] is not None:
        minor(data["expected_pool_version"], field="expected_pool_version")
    reason_code(data["reason_code"])
    note = data["note"]
    if not isinstance(note, str) or not note.strip() or len(note.strip()) > 5000:
        raise PayoutValidationError("invalid_cancellation_note")
    return {**data, "operation_id": operation, "note": note.strip()}


def command_digest(action, obligation_id, data):
    # G1 deliberately freezes the body alone for this durable command. Scope and
    # actor are separately checked against the immutable revision on replay.
    if action == "obligation.cancel":
        return fingerprint(cancellation_command(data))
    return fingerprint({"action": action, "obligation_id": obligation_id, "body": data})
