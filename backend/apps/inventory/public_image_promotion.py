"""Promote one validated snapshot, without ever replacing a final public image."""

from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings

from apps.evidence.image_validation import image_mime_from_bytes
from apps.evidence.storage import StorageUnavailable


def _snapshot(client, key, result):
    try:
        response = client.get_object(Bucket=settings.PUBLIC_IMAGE_BUCKET, Key=key)
    except ClientError as exc:
        if (exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 404
                or exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}):
            return result("missing", None), None, None
        raise
    body = response["Body"]
    try:
        data = body.read(settings.PUBLIC_IMAGE_MAX_BYTES + 1)
    finally:
        body.close()
    size = len(data)
    if not size:
        return result("empty", size), None, None
    if size > settings.PUBLIC_IMAGE_MAX_BYTES:
        return result("too_large", size), None, None
    content_type = response.get("ContentType", "").split(";", 1)[0].strip().lower()
    mime = image_mime_from_bytes(data)
    extensions = settings.PUBLIC_IMAGE_ALLOWED_MIME.get(content_type, ())
    if mime != content_type or not extensions or not key.lower().endswith(tuple(extensions)):
        return result("invalid_image", size), None, None
    return result("ok", size), data, content_type


def _snapshot_after_upload(storage, client, key, attempts=10, delay_seconds=0.2):
    """Retry only absent objects; zero bytes and invalid uploads fail immediately."""
    for attempt in range(attempts):
        snapshot = _snapshot(client, key, storage.FinalizeResult)
        if snapshot[0].status != "missing" or attempt == attempts - 1:
            return snapshot
        storage.time.sleep(delay_seconds)


def finalize(storage, object_key):
    """POST and PUT share the same bounded validation and conditional promotion.

    Read the body once: a client replacing staging during validation cannot change
    the bytes we promote. If another finalizer wins, validate and size its final
    object instead. No database lock is held across these object-store calls.
    """
    client = storage._client()
    staged = storage.staging_key(object_key)
    try:
        existing, _, _ = _snapshot(client, object_key, storage.FinalizeResult)
        if existing.status != "missing":
            if existing.status == "ok":
                storage.delete_object(staged)
            return existing
        checked, data, content_type = _snapshot_after_upload(storage, client, staged)
        if checked.status != "ok":
            if checked.status != "missing":
                storage.delete_object(staged)
            return checked
        try:
            client.put_object(Bucket=settings.PUBLIC_IMAGE_BUCKET, Key=object_key,
                              Body=data, ContentType=content_type, IfNoneMatch="*")
        except ClientError as exc:
            if (exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode") != 412
                    and exc.response.get("Error", {}).get("Code") != "PreconditionFailed"):
                raise
        # Size the winning immutable object, including after a raced promotion.
        final, _, _ = _snapshot_after_upload(storage, client, object_key)
        if final.status == "ok":
            storage.delete_object(staged)
        return final
    except (BotoCoreError, ClientError, OSError) as exc:
        raise StorageUnavailable from exc
