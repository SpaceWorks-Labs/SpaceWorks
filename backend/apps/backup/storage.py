"""Private storage for age-encrypted archives."""

import hashlib
import logging

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings

from apps.object_storage import delete_all_versions, deletion_contract
from apps.storage_capabilities import CapabilityError, capabilities_for
from apps.storage_capabilities.budget import checkpoint, client_options
from apps.storage_capabilities.deletion import assert_exact_absent, delete_owned_prefix, version_pages

logger = logging.getLogger(__name__)
# Shared by every uploader: apps.*.storage.staging_key() is f"staging/{final_key}".
STAGING_PREFIX = "staging/"

RESTORABLE_HEADERS = (
    "CacheControl", "ContentDisposition", "ContentEncoding", "ContentLanguage",
    "ContentType", "Expires", "WebsiteRedirectLocation",
)


class BackupStorageError(RuntimeError):
    pass


class BackupVerificationError(BackupStorageError):
    pass


class BackupObjectMissing(BackupStorageError):
    pass

def client(*, public_endpoint=False):
    endpoint = settings.AWS_S3_PUBLIC_ENDPOINT_URL if public_endpoint else settings.AWS_S3_ENDPOINT_URL
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
        aws_session_token=getattr(settings, "AWS_SESSION_TOKEN", None) or None,
        region_name=settings.AWS_S3_REGION_NAME,
        config=Config(
            signature_version=settings.AWS_S3_SIGNATURE_VERSION,
            s3={"addressing_style": settings.AWS_S3_ADDRESSING_STYLE},
            **client_options(),
        ),
    )


def private_client():
    s3 = client()
    capabilities_for(s3, settings.AWS_STORAGE_BUCKET_NAME, required=True, role="private")
    return s3


def upload_archive(key, path):
    try:
        with open(path, "rb") as handle:
            s3 = private_client()
            bucket = settings.AWS_STORAGE_BUCKET_NAME
            contract = capabilities_for(s3, bucket, required=True)
            handle.seek(0, 2)
            size = handle.tell()
            handle.seek(0)
            if contract is not None:
                contract.validate_upload_limit(size)
            free = getattr(settings, "SPACEWORKS_DEPLOYMENT_PROFILE", "full") == "free"
            if free:
                maximum = getattr(settings, "FREE_MAX_PROMOTION_BYTES", 16 * 1024 * 1024)
                if type(maximum) is not int or maximum < 1 or size > maximum:
                    raise CapabilityError("storage_free_promotion_requires_external_job")
            checkpoint()
            if free or (contract is not None and contract.multipart is not True):
                s3.put_object(Bucket=bucket, Key=key, Body=handle,
                              ContentLength=size, ContentType="application/octet-stream")
            else:
                s3.upload_fileobj(handle, bucket, key, ExtraArgs={"ContentType": "application/octet-stream"})
    except (BotoCoreError, ClientError, OSError) as exc:
        raise BackupStorageError("The encrypted backup archive could not be stored.") from exc


def open_archive(key):
    try:
        return private_client().get_object(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=key
        )["Body"]
    except (BotoCoreError, ClientError) as exc:
        raise BackupStorageError("The encrypted backup archive could not be opened.") from exc


def delete_archive(key):
    try:
        s3 = private_client()
        delete_all_versions(
            s3, bucket=settings.AWS_STORAGE_BUCKET_NAME, key=key
        )
        return True
    except (BotoCoreError, ClientError, CapabilityError):
        logger.warning("backup_archive_delete_failed")
        return False


def delete_archive_prefix(prefix):
    """Delete a caller-owned staging directory and verify it is empty."""
    try:
        s3 = private_client()
        bucket = settings.AWS_STORAGE_BUCKET_NAME
        delete_owned_prefix(s3, bucket=bucket, prefix=prefix,
                            never_versioned=deletion_contract(s3, bucket))
        return True
    except (BotoCoreError, ClientError, CapabilityError):
        logger.warning("backup_archive_prefix_delete_failed")
        return False


def ensure_versioning_or_quiescence(bucket):
    """Inspect without provisioning or treating an outage as unversioned."""
    s3 = client()
    try:
        contract = capabilities_for(s3, bucket, required=True)
        if contract is not None:
            if contract.versioning == "unknown":
                raise CapabilityError("storage_versioning_unknown")
            return "versioned" if contract.versioning == "enabled" else "quiesced"
        checkpoint()
        status = s3.get_bucket_versioning(Bucket=bucket).get("Status")
        if status == "Enabled":
            return "versioned"
        if status in {None, "Suspended"}:
            return "quiesced"
        raise CapabilityError("storage_versioning_unknown")
    except (BotoCoreError, ClientError, CapabilityError) as exc:
        raise BackupStorageError("Storage capture capability could not be verified.") from exc


def download_object(bucket, key, destination, *, versioned):
    """Capture one object, falling back to its staging copy.

    Every uploader presigns `staging/{key}` and only promotes the bytes to `key`
    when a workflow consumes them, so an uploaded-but-unconsumed object exists
    ONLY in staging while its row already names the final key. Capture used to
    treat that as fatal, meaning a single pending upload could block a tenant
    backup or migration. The staged bytes are recorded under the FINAL key so a
    restore lands them where every app's read path looks first; promotion still
    validates them, because each finalizer validates the final object when it
    finds one.
    """
    try:
        return _download_object(bucket, key, destination, versioned=versioned)
    except BackupObjectMissing:
        if key.startswith(STAGING_PREFIX):
            raise
        staged = _download_object(
            bucket, f"{STAGING_PREFIX}{key}", destination, versioned=versioned
        )
        logger.warning(
            "backup_captured_staged_object",
            extra={"bucket": bucket, "key": key},
        )
        return {**staged, "key": key}


def assert_object_absent(bucket, key):
    """Inspect a retention tombstone using the verified bucket history class."""
    try:
        s3 = client()
        assert_exact_absent(s3, bucket=bucket, key=key,
                            never_versioned=deletion_contract(s3, bucket))
    except (BotoCoreError, ClientError, CapabilityError) as exc:
        raise BackupStorageError("Expired storage object absence could not be proved.") from exc


def _download_object(bucket, key, destination, *, versioned):
    s3 = client()
    params = {"Bucket": bucket, "Key": key}
    version_id = ""
    body = None
    try:
        capabilities_for(s3, bucket, required=True)
        if versioned:
            head_missing = False
            try:
                checkpoint()
                version_id = s3.head_object(**params).get("VersionId") or ""
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code")
                status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
                if code not in {"404", "NoSuchKey", "NotFound"} and status != 404:
                    raise
                head_missing = True
                version_id = _latest_retained_version(s3, bucket, key)
            if not version_id:
                if head_missing:
                    raise BackupObjectMissing("Versioned object was not found.")
                raise BackupStorageError("Version-enabled bucket returned no object version ID.")
            params["VersionId"] = version_id
        checkpoint()
        response = s3.get_object(**params)
        body = response["Body"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        with destination.open("wb") as handle:
            while chunk := body.read(1024 * 1024):
                checkpoint()
                handle.write(chunk)
                digest.update(chunk)
        if destination.stat().st_size != response["ContentLength"]:
            raise BackupStorageError("Captured object size did not match storage metadata.")
        return {
            "key": key,
            "version_id": version_id,
            "size": destination.stat().st_size,
            "sha256": digest.hexdigest(),
            "metadata": response.get("Metadata", {}),
            "content_type": response.get("ContentType", ""),
            "headers": {
                name: response[name] for name in RESTORABLE_HEADERS
                if name in response and response[name] not in (None, "")
            },
        }
    except BackupStorageError:
        raise
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound", "NoSuchVersion"}:
            raise BackupObjectMissing("Storage object was not found.") from exc
        raise BackupStorageError("Could not capture storage object.") from exc
    except (BotoCoreError, OSError, CapabilityError) as exc:
        raise BackupStorageError(f"Could not capture storage object {key}.") from exc
    finally:
        if body is not None:
            body.close()


def _latest_retained_version(s3, bucket, key):
    for page in version_pages(s3, bucket=bucket, prefix=key):
        for item in page.get("Versions", ()):
            if item.get("Key") == key:
                return item.get("VersionId") or ""
    return ""


from .storage_promotion import create_final_from_staging, final_locator, object_exists, staging_locator, stream_verify, upload_staging  # noqa: E402,F401
