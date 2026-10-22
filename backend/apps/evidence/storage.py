from dataclasses import dataclass
import logging
import uuid

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings

from apps.evidence.image_validation import image_mime_from_bytes
from apps.object_storage import delete_all_versions
from apps.storage_capabilities import CapabilityError, capabilities_for
from apps.storage_capabilities.budget import checkpoint, client_options
from apps.storage_capabilities.presigning import presign_upload
from apps.storage_capabilities.runtime import configured_contracts
from apps.storage_capabilities.promotion import promote


logger = logging.getLogger(__name__)


class StorageUnavailable(Exception):
    pass


class EvidenceObjectValidationError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class EvidenceValidationResult:
    size: int
    content_type: str

def _s3_client(endpoint_url):
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
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


def _client():
    client = _s3_client(settings.AWS_S3_ENDPOINT_URL)
    capabilities_for(client, settings.AWS_STORAGE_BUCKET_NAME, required=True, role="private")
    return client


def _public_client():
    return _s3_client(settings.AWS_S3_PUBLIC_ENDPOINT_URL)


def evidence_object_key(makerspace_id, evidence_type):
    return f"evidence/{makerspace_id}/{evidence_type}/{uuid.uuid4().hex}"


def staging_key(final_key):
    return f"staging/{final_key}"


def delete_object(object_key):
    try:
        delete_all_versions(
            _client(), bucket=settings.AWS_STORAGE_BUCKET_NAME, key=object_key
        )
        return True
    except (BotoCoreError, ClientError, CapabilityError):
        logger.warning("evidence_object_delete_failed")
        return False


def delete_object_strict(object_key, *, operation_key=None):
    """Delete every version and report whether a current object was visible."""
    existed = object_exists(object_key)
    try:
        delete_all_versions(
            _client(),
            bucket=settings.AWS_STORAGE_BUCKET_NAME,
            key=object_key,
            require_version_listing=True,
            **({"operation_key": operation_key} if operation_key is not None else {}),
        )
    except (BotoCoreError, ClientError, CapabilityError) as exc:
        raise StorageUnavailable from exc
    return "deleted" if existed else "absent_or_version_only"


def copy_object(source_key, dest_key):
    def validate(snapshot, size):
        mime = image_mime_from_bytes(snapshot.read(settings.EVIDENCE_MAX_BYTES + 1))
        if mime not in settings.EVIDENCE_ALLOWED_MIME:
            raise EvidenceObjectValidationError("invalid_image", "Evidence object is not a valid image.")
        return mime

    try:
        promote(
            _client(), source_bucket=settings.AWS_STORAGE_BUCKET_NAME,
            source_key=source_key, destination_bucket=settings.AWS_STORAGE_BUCKET_NAME,
            destination_key=dest_key, max_bytes=settings.EVIDENCE_MAX_BYTES,
            validate=validate,
        )
    except (BotoCoreError, ClientError, CapabilityError, OSError) as exc:
        raise StorageUnavailable from exc


def finalize_upload(evidence, max_bytes):
    from django.db import transaction
    from apps.evidence.finalization_completed import completed_result

    if transaction.get_connection().in_atomic_block:
        completed = completed_result(evidence)
        if completed is not None:
            # Replay may recreate staging through a still-valid presign. Delete it
            # after the domain transaction releases its locks; never promote again.
            transaction.on_commit(lambda: delete_object(staging_key(evidence.object_key)))
            return completed
    from apps.evidence.finalization import FinalizationInProgress
    from apps.evidence.finalization import finalize_upload as finalize_evidence_upload

    try:
        return finalize_evidence_upload(evidence, max_bytes)
    except FinalizationInProgress as exc:
        raise StorageUnavailable from exc


def presigned_upload(object_key, content_type):
    try:
        return presign_upload(
            _public_client(), backend_client=_client(),
            bucket=settings.AWS_STORAGE_BUCKET_NAME, key=staging_key(object_key),
            content_type=content_type, max_bytes=settings.EVIDENCE_MAX_BYTES,
            ttl=settings.EVIDENCE_URL_TTL_SECONDS, requested=settings.STORAGE_PRESIGN_METHOD,
        )
    except (BotoCoreError, ClientError, CapabilityError) as exc:
        raise StorageUnavailable from exc


def uses_put_uploads():
    """Resolve accounting policy without creating an SDK client under a row lock."""
    requested = settings.STORAGE_PRESIGN_METHOD
    if requested in {"put", "post"}:
        return requested == "put"
    contract = configured_contracts().get("private")
    if contract is None:
        raise CapabilityError("storage_auto_requires_capability_contract")
    return contract.presign_method(requested) == "put"


def validate_evidence_object(object_key):
    s3 = _client()
    checkpoint()
    try:
        head = s3.head_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=object_key)
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
            raise EvidenceObjectValidationError("missing", "Evidence object was not found.") from None
        raise StorageUnavailable from exc
    except BotoCoreError as exc:
        raise StorageUnavailable from exc
    size = int(head["ContentLength"])
    if size == 0:
        raise EvidenceObjectValidationError("empty", "Evidence object is empty.")
    if size > settings.EVIDENCE_MAX_BYTES:
        raise EvidenceObjectValidationError(
            "too_large", "Evidence object exceeds the size limit."
        )

    body = None
    try:
        params = {"Bucket": settings.AWS_STORAGE_BUCKET_NAME, "Key": object_key}
        if head.get("VersionId") and head["VersionId"] != "null":
            params["VersionId"] = head["VersionId"]
        elif head.get("ETag"):
            params["IfMatch"] = head["ETag"]
        else:
            raise StorageUnavailable("Evidence snapshot could not be pinned.")
        checkpoint()
        body = s3.get_object(**params)["Body"]
        data = body.read(settings.EVIDENCE_MAX_BYTES + 1)
    except (BotoCoreError, ClientError, OSError) as exc:
        raise StorageUnavailable from exc
    finally:
        if body is not None:
            body.close()
    if len(data) != size:
        raise EvidenceObjectValidationError("size_changed", "Evidence object size changed.")

    content_type = image_mime_from_bytes(data)
    if content_type not in settings.EVIDENCE_ALLOWED_MIME:
        raise EvidenceObjectValidationError(
            "invalid_image", "Evidence object is not a valid image."
        )
    return EvidenceValidationResult(size=size, content_type=content_type)

def presigned_get_url(object_key):
    try:
        _client()  # verify the private role using the backend API identity
        return _public_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.AWS_STORAGE_BUCKET_NAME, "Key": object_key},
            ExpiresIn=settings.EVIDENCE_URL_TTL_SECONDS,
        )
    except (BotoCoreError, ClientError) as exc:
        raise StorageUnavailable from exc


def object_exists(object_key):
    try:
        checkpoint()
        _client().head_object(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Key=object_key,
        )
    except ClientError as exc:
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        code = exc.response.get("Error", {}).get("Code")
        if status == 404 or code in {"404", "NoSuchKey", "NotFound"}:
            return False
        raise StorageUnavailable from exc
    except BotoCoreError as exc:
        raise StorageUnavailable from exc
    return True


def object_size(object_key):
    try:
        checkpoint()
        response = _client().head_object(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Key=object_key,
        )
    except ClientError as exc:
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        code = exc.response.get("Error", {}).get("Code")
        if status == 404 or code in {"404", "NoSuchKey", "NotFound"}:
            return None
        raise StorageUnavailable from exc
    except BotoCoreError as exc:
        raise StorageUnavailable from exc

    return int(response["ContentLength"])
