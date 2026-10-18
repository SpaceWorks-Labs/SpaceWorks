"""Replay receipts retain safe metadata only, never a second copy of deleted PII."""
from django.utils.crypto import salted_hmac

from .crypto import canonical
from .errors import SavedDetailsError
from .models import SavedDetailCommandReceipt


def request_digest(path, body):
    return salted_hmac("saved-details-command-v1", canonical([path, body]), algorithm="sha256").hexdigest()


def replay(user_id, operation_id, digest, *, key=None):
    row = SavedDetailCommandReceipt.objects.filter(user_id=user_id, operation_uuid=operation_id).first()
    if row is None:
        return None
    if row.request_sha256 != digest:
        raise SavedDetailsError("idempotency_conflict", "Use a new operation ID for changed details.", 409)
    return dict(row.response_metadata)


def remember(user_id, operation_id, digest, response, key):
    row = SavedDetailCommandReceipt(user_id=user_id, operation_uuid=operation_id, request_sha256=digest)
    row.response_metadata = {name: value for name, value in response.items()
                             if name in {"field_key", "version", "deleted", "asset_id", "state", "status_url", "job_id"}}
    row.save()
    return response
