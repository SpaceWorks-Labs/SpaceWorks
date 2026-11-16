"""Capability-configured private documents share staging and create-only promotion."""
from botocore.exceptions import ClientError
from django.conf import settings

from apps.storage_capabilities.contracts import CapabilityError
from apps.storage_capabilities.presigning import presign_upload
from apps.storage_capabilities.promotion import promote


def promotion_limit(max_bytes):
    if settings.SPACEWORKS_DEPLOYMENT_PROFILE == "free":
        return min(max_bytes, settings.FREE_MAX_PROMOTION_BYTES)
    return max_bytes


def presign(storage, key, content_type, max_bytes):
    return presign_upload(storage._public_client(), backend_client=storage._client(),
        bucket=settings.AWS_STORAGE_BUCKET_NAME, key=storage.staging_key(key),
        content_type=content_type, max_bytes=promotion_limit(max_bytes),
        ttl=settings.EVIDENCE_URL_TTL_SECONDS, requested=settings.STORAGE_PRESIGN_METHOD)


def finalize(storage, key, max_bytes):
    from botocore.exceptions import BotoCoreError
    from apps.evidence.storage import StorageUnavailable
    try:
        return _finalize(storage, key, max_bytes)
    except (BotoCoreError, ClientError, OSError) as exc:
        raise StorageUnavailable from exc


def _finalize(storage, key, max_bytes):
    maximum = promotion_limit(max_bytes)
    client = storage._client()
    existing = storage.object_size(key)
    if existing is not None:
        return existing
    source = storage.staging_key(key)
    try:
        head = client.head_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=source)
    except ClientError as exc:
        if str(exc.response.get("Error", {}).get("Code")) in {"404", "NoSuchKey", "NotFound"}:
            return None
        raise
    size = head["ContentLength"]
    if size > maximum and size <= max_bytes:
        raise CapabilityError("storage_free_promotion_limit_reached")
    if not 1 <= size <= maximum:
        return size  # The domain's existing validation renders the size refusal.
    try:
        result = promote(client, source_bucket=settings.AWS_STORAGE_BUCKET_NAME, source_key=source,
            destination_bucket=settings.AWS_STORAGE_BUCKET_NAME, destination_key=key,
            max_bytes=maximum, expected_etag=head.get("ETag"))
    except CapabilityError as exc:
        if exc.code == "storage_final_already_exists":
            return storage.object_size(key)
        raise
    from apps.object_storage import delete_all_versions
    delete_all_versions(client, bucket=settings.AWS_STORAGE_BUCKET_NAME, key=source)
    return result["size"]
