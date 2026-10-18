"""Remote byte operations for backup staging and create-only promotion."""

import hashlib
import hmac

from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings

from apps.storage_capabilities import CapabilityError
from apps.storage_capabilities.budget import checkpoint
from apps.storage_capabilities.promotion import promote


CHUNK_SIZE = 1024 * 1024


def staging_locator(artifact_id):
    return f"backup-archives/staging/{artifact_id}.tar.age"


def final_locator(artifact_id):
    return f"backup-archives/deployment/{artifact_id}.tar.age"


def upload_staging(key, path):
    from apps.backup import storage

    storage.upload_archive(key, path)


def stream_verify(key, *, expected_size, expected_sha256):
    from apps.backup import storage

    body = None
    try:
        checkpoint()
        body = storage.private_client().get_object(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=key
        )["Body"]
        digest = hashlib.sha256()
        size = 0
        while chunk := body.read(CHUNK_SIZE):
            checkpoint()
            size += len(chunk)
            if size > expected_size:
                raise storage.BackupVerificationError("The stored archive exceeds its expected size.")
            digest.update(chunk)
    except (BotoCoreError, ClientError, OSError, CapabilityError) as exc:
        raise storage.BackupStorageError(
            "The backup archive could not be streamed for verification."
        ) from exc
    finally:
        if body is not None and hasattr(body, "close"):
            body.close()
    actual = digest.hexdigest()
    if size != expected_size or not hmac.compare_digest(actual, expected_sha256):
        raise storage.BackupVerificationError(
            "The stored backup archive does not match its expected size and sha256."
        )
    return size, actual


def create_final_from_staging(staging_key, final_key):
    """Copy staging into a destination protected by `If-None-Match: *`.

    The staging bytes are spooled to a private temporary file first. Handing the GET's
    StreamingBody straight to `put_object` cannot work: botocore seeks the body to
    compute request checksums (io.UnsupportedOperation on modern botocore) and, over
    plain http, reads it to sign the payload, leaving nothing to send. A seekable file
    costs one archive's worth of local disk, which the build already needed.
    """
    from apps.backup import storage

    try:
        s3 = storage.private_client()
        bucket = settings.AWS_STORAGE_BUCKET_NAME
        checkpoint()
        size = s3.head_object(Bucket=bucket, Key=staging_key)["ContentLength"]
        if getattr(settings, "SPACEWORKS_DEPLOYMENT_PROFILE", "full") == "free":
            maximum = getattr(settings, "FREE_MAX_PROMOTION_BYTES", 16 * 1024 * 1024)
            if type(maximum) is not int or maximum < 1 or size > maximum:
                raise CapabilityError("storage_free_promotion_requires_external_job")
        else:
            maximum = size
        promote(s3, source_bucket=bucket, source_key=staging_key,
                destination_bucket=bucket, destination_key=final_key,
                max_bytes=maximum, content_type="application/octet-stream")
    except (BotoCoreError, ClientError, OSError, CapabilityError) as exc:
        if isinstance(exc, CapabilityError) and exc.code == "storage_final_already_exists":
            raise storage.BackupStorageError("The immutable final backup locator already exists.") from exc
        raise storage.BackupStorageError(
            "The backup staging object could not be promoted."
        ) from exc


def object_exists(key):
    from apps.backup import storage

    try:
        checkpoint()
        storage.private_client().head_object(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=key
        )
        return True
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if code in {"404", "NoSuchKey", "NotFound"} or status == 404:
            return False
        raise storage.BackupStorageError(
            "The backup object locator could not be inspected."
        ) from exc
    except (BotoCoreError, CapabilityError) as exc:
        raise storage.BackupStorageError(
            "The backup object locator could not be inspected."
        ) from exc
