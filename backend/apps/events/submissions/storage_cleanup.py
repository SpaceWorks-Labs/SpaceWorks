"""Delete every owned object version and multipart upload, then prove absence.

Returns one tally per key (versions, delete markers, multipart uploads removed) so the
caller can write a durable `SubmissionStorageCleanupReceipt` once absence is proven.
"""
from .errors import SubmissionError


def delete_keys(storage, keys):
    wanted = {key for key in keys if key}
    tallies = {}
    try:
        for key in sorted(wanted):
            tally = tallies.setdefault(key, {"versions": 0, "markers": 0, "uploads": 0})
            paginator = storage.client.get_paginator("list_object_versions")
            for page in paginator.paginate(Bucket=storage.bucket, Prefix=key):
                versions = [{"Key": v["Key"], "VersionId": v["VersionId"]}
                            for name in ("Versions", "DeleteMarkers") for v in page.get(name, []) if v["Key"] == key]
                tally["versions"] += sum(1 for v in page.get("Versions", []) if v["Key"] == key)
                tally["markers"] += sum(1 for v in page.get("DeleteMarkers", []) if v["Key"] == key)
                for start in range(0, len(versions), 1000):
                    result = storage.client.delete_objects(Bucket=storage.bucket,
                        Delete={"Objects": versions[start:start + 1000], "Quiet": True})
                    if result.get("Errors"):
                        raise SubmissionError("storage_cleanup_pending", 503)
            storage.client.delete_object(Bucket=storage.bucket, Key=key)
            uploads = storage.client.get_paginator("list_multipart_uploads")
            for page in uploads.paginate(Bucket=storage.bucket, Prefix=key):
                for upload in page.get("Uploads", []):
                    if upload["Key"] == key:
                        tally["uploads"] += 1
                        storage.client.abort_multipart_upload(Bucket=storage.bucket, Key=key, UploadId=upload["UploadId"])
            # A normal delete in a versioned bucket creates a marker. Remove it
            # too and fail closed if any concurrent/new version remains.
            for page in paginator.paginate(Bucket=storage.bucket, Prefix=key):
                for marker in page.get("DeleteMarkers", []):
                    if marker["Key"] == key:
                        storage.client.delete_object(Bucket=storage.bucket, Key=key, VersionId=marker["VersionId"])
                if any(v["Key"] == key for v in page.get("Versions", [])):
                    raise SubmissionError("storage_cleanup_pending", 503)
            for page in uploads.paginate(Bucket=storage.bucket, Prefix=key):
                if any(v["Key"] == key for v in page.get("Uploads", [])):
                    raise SubmissionError("storage_cleanup_pending", 503)
            for page in paginator.paginate(Bucket=storage.bucket, Prefix=key):
                if any(v["Key"] == key for name in ("Versions", "DeleteMarkers") for v in page.get(name, [])):
                    raise SubmissionError("storage_cleanup_pending", 503)
            try:
                storage.client.head_object(Bucket=storage.bucket, Key=key)
            except Exception as exc:
                if getattr(exc, "response", {}).get("Error", {}).get("Code") not in {"404", "NoSuchKey", "NotFound"}:
                    raise
            else:
                raise SubmissionError("storage_cleanup_pending", 503)
    except SubmissionError:
        raise
    except Exception as exc:
        raise SubmissionError("storage_cleanup_pending", 503) from exc
    return tallies


def record_receipts(*, makerspace_id, event_id, asset_uuid, tallies):
    """Append the proof; replays of the same key are a no-op (append-only, FK-free)."""
    from hashlib import sha256
    from django.utils import timezone
    from apps.events.models_r2_l2 import SubmissionStorageCleanupReceipt
    now = timezone.now()
    for key, tally in tallies.items():
        SubmissionStorageCleanupReceipt.objects.get_or_create(
            asset_uuid=asset_uuid, key_sha256=sha256(key.encode()).hexdigest(), defaults={
                "makerspace_id_snapshot": makerspace_id, "event_id_snapshot": event_id,
                "versions_deleted": tally["versions"], "markers_deleted": tally["markers"],
                "uploads_aborted": tally["uploads"], "verified_absent_at": now})
