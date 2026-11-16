"""Private staging for capability-configured images, with legacy locator reads."""
from botocore.exceptions import ClientError
from django.conf import settings

from apps.storage_capabilities.contracts import CapabilityError
from apps.storage_capabilities.presigning import (
    presign_upload, public_image_staging, public_image_staging_candidates,
)
from apps.storage_capabilities.promotion import promote


def presign(storage, key, content_type):
    locator = public_image_staging(key, private_bucket=settings.AWS_STORAGE_BUCKET_NAME)
    return presign_upload(storage._public_client(), backend_client=storage._client(),
        bucket=locator.bucket, key=locator.key, content_type=content_type,
        max_bytes=settings.PUBLIC_IMAGE_MAX_BYTES, ttl=settings.PUBLIC_IMAGE_URL_TTL_SECONDS,
        requested=settings.STORAGE_PRESIGN_METHOD)


def finalize(storage, key):
    from botocore.exceptions import BotoCoreError
    from apps.evidence.storage import StorageUnavailable
    try:
        return _finalize(storage, key)
    except (BotoCoreError, ClientError, OSError) as exc:
        raise StorageUnavailable from exc


def _finalize(storage, key):
    from .public_image_promotion import _snapshot
    from apps.evidence.image_validation import image_mime_from_bytes
    client = storage._client()
    existing, _, _ = _snapshot(client, key, storage.FinalizeResult)
    if existing.status != "missing":
        return existing
    candidates = public_image_staging_candidates(key, private_bucket=settings.AWS_STORAGE_BUCKET_NAME,
                                               public_bucket=settings.PUBLIC_IMAGE_BUCKET)
    for locator in candidates:
        try:
            head = client.head_object(Bucket=locator.bucket, Key=locator.key)
        except ClientError as exc:
            if str(exc.response.get("Error", {}).get("Code")) in {"404", "NoSuchKey", "NotFound"}:
                continue
            raise
        expected_type = head.get("ContentType", "").split(";", 1)[0].lower()

        def validate(spool, size):
            mime = image_mime_from_bytes(spool.read(settings.PUBLIC_IMAGE_MAX_BYTES + 1))
            extensions = settings.PUBLIC_IMAGE_ALLOWED_MIME.get(mime, ())
            if mime != expected_type or not extensions or not key.lower().endswith(tuple(extensions)):
                raise CapabilityError("storage_invalid_public_image")
            return mime

        try:
            result = promote(client, source_bucket=locator.bucket, source_key=locator.key,
                destination_bucket=settings.PUBLIC_IMAGE_BUCKET, destination_key=key,
                max_bytes=settings.PUBLIC_IMAGE_MAX_BYTES, validate=validate, expected_etag=head.get("ETag"))
        except CapabilityError as exc:
            if exc.code == "storage_final_already_exists":
                return _snapshot(client, key, storage.FinalizeResult)[0]
            if exc.code == "storage_invalid_public_image":
                return storage.FinalizeResult("invalid_image", head.get("ContentLength"))
            raise
        from apps.object_storage import delete_all_versions
        delete_all_versions(client, bucket=locator.bucket, key=locator.key)
        return storage.FinalizeResult("ok", result["size"])
    return storage.FinalizeResult("missing", None)
