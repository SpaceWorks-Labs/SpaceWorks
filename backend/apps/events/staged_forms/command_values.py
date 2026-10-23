"""Model-free wire identities shared by commands, reminders and adapters."""
from datetime import UTC


def canonical_utc(value):
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Use an aware timestamp.")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def form_intent_status(*, slot, operation_id, intent_id):
    return {"slot": slot, "operation_id": str(operation_id),
        "intent_id": str(intent_id) if intent_id else None,
        "state": "pending" if intent_id else "not_requested", "fields": {},
        "status_url": f"/api/v1/member/saved-details/save-intents/{operation_id}/" if intent_id else None}


def rsvp_identity(row):
    return f"application:{row.pk}:offer:{row.decision_revision}:due:{canonical_utc(row.rsvp_due_at)}"
