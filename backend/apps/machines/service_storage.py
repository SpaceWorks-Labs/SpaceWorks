"""Private attachment storage for machine service requests."""
from django.utils.translation import gettext
from dataclasses import dataclass
import logging
import uuid

from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit
from apps.evidence.storage import StorageUnavailable
from apps.maker_file_formats import (
    STRICT_MIME_BY_EXTENSION,
    allowed_pair,
    extension_from_name,
    has_required_signature,
    sniff_pdf_or_image,
)
from apps.machines import storage as machine_storage
from apps.machines.models import Machine, ServiceRequestFile
from apps.machines.service_file_policies import get_policy, policy_for_machine, policy_for_queue
from apps.makerspaces import limits  # noqa: F401  (patched here by tests; used by the attach module)
from apps.object_storage import delete_all_versions

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ServiceObjectValidationResult:
    size: int
    content_type: str


def _client():
    return machine_storage._client()


def _public_client():
    return machine_storage._public_client()


def service_object_key(makerspace_id, context_id):
    return f"machine/{makerspace_id}/{context_id}/service/{uuid.uuid4().hex}"


def staging_key(object_key):
    return machine_storage.staging_key(object_key)


def validate_upload_declaration(policy, filename, content_type):
    ext = extension_from_name(filename)
    if not allowed_pair(ext, content_type, policy.allowed_extensions, policy.allowed_mimes):
        raise ValidationError({"filename": gettext("Unsupported attachment extension or content type.")}, code="invalid_attachment")


def policy_for_file(file):
    """Use the immutable policy snapshot retained with the staged file."""
    return get_policy(file.file_policy_name, file.file_policy_version)


def create_staged_file(service_request, *, actor, filename, content_type):
    if service_request.queue_id:
        queue = service_request.queue
        machine, policy, context_id = None, policy_for_queue(queue), f"queue-{queue.pk}"
        makerspace = queue.makerspace
    else:
        machine = Machine.objects.get(pk=service_request.bucket.machine_id)
        queue, policy, context_id, makerspace = None, policy_for_machine(machine), machine.pk, machine.makerspace
    validate_upload_declaration(policy, filename, content_type)
    upload = ServiceRequestFile.objects.create(
        makerspace=makerspace, machine=machine, queue=queue,
        kind=ServiceRequestFile.Kind.ATTACHMENT,
        object_key=service_object_key(makerspace.pk, context_id),
        content_type=content_type.lower().strip(),
        original_filename=filename,
        owner_user_id=actor.pk,
        file_policy_name=policy.name,
        file_policy_version=policy.version,
    )
    try:
        presigned = presigned_upload(upload.object_key, upload.content_type, policy.max_bytes)
    except Exception:
        upload.delete()
        raise
    audit.record(
        actor, "machine_service.file_staged", makerspace=makerspace,
        target=upload, meta={"request_id": service_request.pk, "file_id": upload.pk},
    )
    return upload, presigned


def create_staged_queue_file(queue, *, actor, filename, content_type, kind=ServiceRequestFile.Kind.MODEL):
    """Stage a public queued-service file before its request exists.

    Public printing uses this during the B4 compatibility period: the queue is
    already authoritative, while the request is only created after upload.
    """
    policy = policy_for_queue(queue)
    validate_upload_declaration(policy, filename, content_type)
    upload = ServiceRequestFile.objects.create(
        makerspace=queue.makerspace, queue=queue,
        kind=kind,
        object_key=service_object_key(queue.makerspace_id, f"queue-{queue.pk}"),
        content_type=content_type.lower().strip(), original_filename=filename,
        owner_user_id=actor.pk, file_policy_name=policy.name,
        file_policy_version=policy.version,
    )
    try:
        presigned = presigned_upload(upload.object_key, upload.content_type, policy.max_bytes)
    except Exception:
        upload.delete()
        raise
    audit.record(
        actor, "machine_service.file_staged", makerspace=queue.makerspace,
        target=upload, meta={"queue_id": queue.pk, "file_id": upload.pk},
    )
    return upload, presigned


def presigned_upload(object_key, content_type, max_bytes):
    try:
        if settings.STORAGE_PRESIGN_METHOD == "put":
            url = _public_client().generate_presigned_url(
                "put_object", Params={
                    "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
                    "Key": staging_key(object_key), "ContentType": content_type,
                }, ExpiresIn=settings.EVIDENCE_URL_TTL_SECONDS,
            )
            return {"url": url, "method": "PUT", "headers": {"Content-Type": content_type}}
        return _public_client().generate_presigned_post(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=object_key,
            Fields={"Content-Type": content_type},
            Conditions=[{"Content-Type": content_type}, ["content-length-range", 1, max_bytes]],
            ExpiresIn=settings.EVIDENCE_URL_TTL_SECONDS,
        )
    except (BotoCoreError, ClientError) as exc:
        raise StorageUnavailable from exc


def object_size(object_key):
    try:
        response = _client().head_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=object_key)
    except ClientError as exc:
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        code = exc.response.get("Error", {}).get("Code")
        if status == 404 or code in {"404", "NoSuchKey", "NotFound"}:
            return None
        raise StorageUnavailable from exc
    except BotoCoreError as exc:
        raise StorageUnavailable from exc
    return int(response["ContentLength"])


def delete_object(object_key):
    try:
        delete_all_versions(
            _client(), bucket=settings.AWS_STORAGE_BUCKET_NAME, key=object_key
        )
    except (BotoCoreError, ClientError):
        logger.exception("Failed to delete machine service object %s.", object_key)


def cleanup_upload(object_key):
    delete_object(object_key)
    delete_object(staging_key(object_key))


def finalize_upload(object_key, max_bytes):
    if settings.STORAGE_PRESIGN_METHOD != "put":
        return object_size(object_key)
    final_size = object_size(object_key)
    if final_size is not None:
        delete_object(staging_key(object_key))
        return final_size
    source = staging_key(object_key)
    size = object_size(source)
    if size is None or not 1 <= size <= max_bytes:
        return size
    try:
        _client().copy_object(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            CopySource={"Bucket": settings.AWS_STORAGE_BUCKET_NAME, "Key": source},
            Key=object_key,
        )
    except (BotoCoreError, ClientError) as exc:
        raise StorageUnavailable from exc
    delete_object(source)
    final_size = object_size(object_key)
    if final_size is None or not 1 <= final_size <= max_bytes:
        delete_object(object_key)
    return final_size


def validate_service_object(file, policy):
    size = object_size(file.object_key)
    if size is None:
        raise ValidationError({"file_id": gettext("Uploaded attachment was not found.")}, code="invalid_attachment")
    if not 1 <= size <= policy.max_bytes:
        raise ValidationError({"file_id": gettext("Uploaded attachment exceeds the size limit.")}, code="invalid_attachment")
    try:
        response = _client().get_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=file.object_key)
        data = response["Body"].read(policy.max_bytes)
        stored_content_type = str(response.get("ContentType", "")).lower().strip()
    except (BotoCoreError, ClientError, OSError) as exc:
        raise StorageUnavailable from exc
    ext = extension_from_name(file.original_filename)
    if not allowed_pair(ext, stored_content_type, policy.allowed_extensions, policy.allowed_mimes):
        raise ValidationError({"file_id": gettext("Attachment extension and content type do not match.")}, code="invalid_attachment")
    sniffed = sniff_pdf_or_image(data)
    strict_mime = STRICT_MIME_BY_EXTENSION.get(ext)
    if strict_mime or sniffed:
        if not strict_mime or stored_content_type != strict_mime or sniffed != strict_mime:
            raise ValidationError({"file_id": gettext("Attachment content does not match its extension.")}, code="invalid_attachment")
        content_type = sniffed
    elif not has_required_signature(ext, data):
        raise ValidationError({"file_id": gettext("Attachment signature is invalid.")}, code="invalid_attachment")
    else:
        content_type = stored_content_type
    return ServiceObjectValidationResult(size=size, content_type=content_type)


def presigned_get_url(object_key):
    try:
        return _public_client().generate_presigned_url(
            "get_object", Params={"Bucket": settings.AWS_STORAGE_BUCKET_NAME, "Key": object_key},
            ExpiresIn=settings.EVIDENCE_URL_TTL_SECONDS,
        )
    except (BotoCoreError, ClientError) as exc:
        raise StorageUnavailable from exc


# Attach/delete live in a sibling module; re-exported so existing imports keep resolving.
from apps.machines.service_storage_attach import delete_staged_file, finalize_file  # noqa: E402,F401
