"""Private-bucket I/O for the card engine. Nothing here is ever public.

Prefixes (all PRIVATE, `backup/object_ownership_registry`):
  card-assets/<ms>/<uuid>        uploaded design artwork, re-encoded server-side
  card-photos/<ms>/<uuid>        programme and event card photos
  card-jobs/<ms>/<job>/<name>    temporary bulk results, deleted 7 days after finishing
  card-fonts/<slug>/<weight>.ttf fetched open-licence font files (deployment-wide)

Client uploads only ever reach `staging/<final key>` through a presign; the final key
is written here by the server after validation (the staging -> final Hard Rule).
"""
import logging

from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings

from apps.evidence import storage as evidence_storage
from apps.evidence.storage import StorageUnavailable

logger = logging.getLogger(__name__)
MAX_OBJECT_BYTES = 200 * 1024 * 1024


def _client():
    return evidence_storage._client()


def put_bytes(key, data, content_type):
    if not data or len(data) > MAX_OBJECT_BYTES:
        raise StorageUnavailable("Card object outside the bounded size.")
    try:
        _client().put_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=key, Body=data, ContentType=content_type)
    except (BotoCoreError, ClientError, OSError) as exc:
        raise StorageUnavailable from exc
    return len(data)


def get_bytes(key, limit=MAX_OBJECT_BYTES):
    body = None
    try:
        body = _client().get_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=key)["Body"]
        data = body.read(limit + 1)
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
            return None
        raise StorageUnavailable from exc
    except (BotoCoreError, OSError) as exc:
        raise StorageUnavailable from exc
    finally:
        if body is not None:
            body.close()
    if len(data) > limit:
        raise StorageUnavailable("Card object larger than expected.")
    return data


def read_optional(key, limit=MAX_OBJECT_BYTES):
    """Rendering reads: a missing or unreachable object renders as a placeholder."""
    if not key:
        return None
    try:
        return get_bytes(key, limit)
    except StorageUnavailable:
        logger.warning("card_object_unreadable")
        return None


def delete(key):
    if not key:
        return
    from apps.object_storage import delete_all_versions
    try:
        delete_all_versions(_client(), bucket=settings.AWS_STORAGE_BUCKET_NAME, key=key)
    except (BotoCoreError, ClientError, OSError) as exc:
        raise StorageUnavailable from exc


def delete_quietly(key):
    try:
        delete(key)
    except StorageUnavailable:
        logger.warning("card_object_delete_deferred")


def signed_url(key, *, filename=None):
    params = {"Bucket": settings.AWS_STORAGE_BUCKET_NAME, "Key": key}
    if filename:
        params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'
    try:
        _client()
        return evidence_storage._public_client().generate_presigned_url(
            "get_object", Params=params, ExpiresIn=settings.EVIDENCE_URL_TTL_SECONDS)
    except (BotoCoreError, ClientError) as exc:
        raise StorageUnavailable from exc


def presign_staging(final_key, content_type, max_bytes):
    from apps.private_uploads import presign
    try:
        return presign(evidence_storage, final_key, content_type, max_bytes)
    except (BotoCoreError, ClientError) as exc:
        raise StorageUnavailable from exc


def take_staging(final_key, max_bytes):
    """Read and remove the staged upload for `final_key`; None when nothing was uploaded."""
    staging = evidence_storage.staging_key(final_key)
    data = get_bytes(staging, max_bytes + 1)
    if data is None:
        return None
    delete_quietly(staging)
    if len(data) > max_bytes:
        raise StorageUnavailable("Upload exceeds the size limit.")
    return data
