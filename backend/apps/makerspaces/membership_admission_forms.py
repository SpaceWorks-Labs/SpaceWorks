"""Shared custom-form validation, serialized at the scoped-PII text boundary."""
import json
import logging

from apps.forms_schema.validation import validate_answers

logger = logging.getLogger(__name__)


def encode_answers(schema, raw):
    snapshot = validate_answers(schema, raw)
    return json.dumps(snapshot, ensure_ascii=False) if snapshot is not None else None


def answers_for(row):
    if not row.application_answers:
        return None
    try:
        snapshot = json.loads(row.application_answers)
    except (ValueError, TypeError):
        logger.warning("membership_application_snapshot_invalid", extra={"request_id": row.pk})
        return None
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("answers"), list):
        return None
    return {key: value for key, value in snapshot.items() if key != "join_fields"}  # O-B2: private extras
