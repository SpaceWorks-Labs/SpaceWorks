"""Replay receipts retain safe metadata only, never a second copy of deleted PII."""
from django.utils.translation import gettext
from django.utils.crypto import salted_hmac
from uuid import UUID

from .crypto import canonical
from .errors import SavedDetailsError
from .models import SavedDetailCommandReceipt, SavedDetailUpdateIntent
from .fields import require_form_slot
from .access import require_owner


def request_digest(path, body):
    return salted_hmac("saved-details-command-v1", canonical([path, body]), algorithm="sha256").hexdigest()


def replay(user_id, operation_id, digest, *, key=None):
    row = SavedDetailCommandReceipt.objects.filter(user_id=user_id, operation_uuid=operation_id).first()
    if row is None:
        return None
    if row.request_sha256 != digest:
        raise SavedDetailsError("idempotency_conflict", gettext("Use a new operation ID for changed details."), 409)
    return dict(row.response_metadata)


def remember(user_id, operation_id, digest, response, key):
    row = SavedDetailCommandReceipt(user_id=user_id, operation_uuid=operation_id, request_sha256=digest)
    row.response_metadata = {name: value for name, value in response.items()
                             if name in {"field_key", "version", "deleted", "asset_id", "state", "status_url", "job_id"}}
    row.save()
    return response


def form_intent_statuses(actor_id, form_operations):
    """Project G's bound IDs-only slot map after ALL insertions in its transaction.

    G retains this result in its outer receipt for replay. Missing rows mean
    not_requested only at initial commit; do not rebuild expired replay receipts.
    The slot map is server-owned, never accepted as an HTTP status selector.
    """
    require_owner(actor_id)
    operations, seen = {}, set()
    for slot, binding in sorted(form_operations.items()):
        require_form_slot(slot)
        try:
            operation = UUID(str(binding["operation_id"]))
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            raise SavedDetailsError("invalid_operation_id", gettext("Use the bound form operation.")) from exc
        if (operation in seen or binding.get("kind") not in {"registration", "application", "role_assignment", "stage_response"}
                or type(binding.get("subject_id")) is not int or binding["subject_id"] <= 0
                or (slot != "base") != (binding["kind"] == "stage_response")):
            raise SavedDetailsError("invalid_subject", gettext("Use the bound form operations."), 409)
        operations[slot] = operation
        seen.add(operation)
    rows = {row.operation_uuid: row for row in SavedDetailUpdateIntent.objects.filter(user_id=actor_id, operation_uuid__in=seen)}
    result = []
    for slot, operation in operations.items():
        row = rows.get(operation)
        binding = form_operations[slot]
        if row and (row.subject_kind, row.subject_id) != (binding["kind"], binding["subject_id"]):
            raise SavedDetailsError("invalid_subject", gettext("This update belongs to another form."), 409)
        result.append({"slot": slot, "operation_id": str(operation), "intent_id": str(row.id) if row else None,
                       "state": row.state if row else "not_requested", "fields": row.field_status if row else {},
                       "status_url": f"/api/v1/member/saved-details/save-intents/{operation}/" if row else None})
    return result
