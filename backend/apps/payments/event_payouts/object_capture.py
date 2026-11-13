"""Retained private finance originals with exact pinned-version verification."""
from hashlib import sha256
from .retention import capture_state
from .attachment_storage import FinanceStorage, asset_bucket
from .errors import require


def capture(row, *, now, storage=None):
    disposition = capture_state(row, now=now)
    require(disposition != "retry_retention", "finance_retention_in_progress", status=409)
    if disposition != "canonical":
        return None
    storage = storage or FinanceStorage(bucket_name=asset_bucket(row.pk))
    # ready/attached always have an immutable verified final object. There is no
    # unconsumed/infected staging fallback. Missing live bytes abort the archive.
    data = storage.read(row.object_key, version=row.final_version_id or None, maximum=row.expected_bytes)
    require(len(data) == row.actual_bytes and sha256(data).hexdigest() == row.sha256,
            "finance_capture_integrity_failed", status=503)
    return data


def collect_keys(makerspace, add, *, include_coordination=True):
    from .attachment_models import FinanceAttachment
    for row in FinanceAttachment.objects.filter(makerspace=makerspace).iterator(chunk_size=100):
        add(row.object_key)
        if include_coordination:
            add(row.staging_key)
