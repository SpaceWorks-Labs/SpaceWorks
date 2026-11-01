"""Job files checked against the strict `maker_formats` registry (#142 OQ-12).

Each machine type accepts the registry groups its policy names (3D printers: models;
lasers and vinyl: 2D vectors; CNC: toolpaths, vectors and CAD; PCB mills: fabrication
outputs), plus screenshots. Uploads land on the staging key through the presign
(Hard Rule); attaching promotes the object once and reads it through exact, versioned
range reads -- magic bytes and container structure, never a full parse -- before it is
bound to the job. A file that fails never attaches.
"""

from django.conf import settings
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit
from apps.maker_formats.errors import FormatError
from apps.maker_formats.range_reader import S3RangeReader
from apps.maker_formats.registry import extension_from_name
from apps.maker_formats.upload_policy import upload_spec, validate_upload
from apps.machines import job_policy
from apps.machines.models import ServiceRequestFile

POLICY_NAME, POLICY_VERSION = "maker_formats", 1
IMAGE_GROUP = "images"


def groups_for(queue, kind):
    if kind == ServiceRequestFile.Kind.SCREENSHOT:
        return (IMAGE_GROUP,)
    return job_policy.file_groups(queue.makerspace, queue.machine_type)


def resolve(filename, content_type, groups):
    """(spec, cap, group) for the first accepted group, or a typed 400."""
    last = "unsupported_format"
    for group in groups:
        try:
            spec, cap, group = upload_spec(filename, group=group, subtype="auto", declared_mime=content_type)
            return spec, cap, group
        except FormatError as exc:
            last = exc.code
    raise ValidationError({"file": "This file type is not accepted for this machine.", "code": last})


def stage_job_file(queue, actor, *, filename, content_type, kind):
    from apps.machines.service_storage import presigned_upload, service_object_key
    kind = ServiceRequestFile.Kind.SCREENSHOT if kind == "screenshot" else ServiceRequestFile.Kind.MODEL
    spec, cap, group = resolve(filename, content_type, groups_for(queue, kind))
    upload = ServiceRequestFile.objects.create(
        makerspace=queue.makerspace, queue=queue, kind=kind,
        object_key=service_object_key(queue.makerspace_id, f"queue-{queue.pk}"),
        content_type=content_type.lower().strip(), original_filename=filename, owner_user_id=actor.pk,
        file_policy_name=POLICY_NAME, file_policy_version=POLICY_VERSION,
    )
    try:
        presigned = presigned_upload(upload.object_key, upload.content_type, cap)
    except Exception:
        upload.delete()
        raise
    audit.record(actor, "machine_service.file_staged", makerspace=queue.makerspace, target=upload,
                 meta={"queue_id": queue.pk, "file_id": upload.pk})
    return upload, presigned, {"group": group, "max_bytes": cap, "preview": spec.preview}


def _reader(file, size):
    from apps.machines.service_storage import _client
    head = _client().head_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=file.object_key)
    return S3RangeReader(_client(), bucket=settings.AWS_STORAGE_BUCKET_NAME, key=file.object_key, size=size,
                         version_id=head.get("VersionId"), etag=head.get("ETag"))


def validate_job_object(file):
    """Promote the staged object, then check it against its registry entry."""
    from apps.machines.service_storage import ServiceObjectValidationResult, finalize_upload
    queue = file.queue
    if queue is None:
        raise ValidationError({"file_id": "Attachment is unavailable for this request."}, code="invalid_attachment")
    spec, cap, group = resolve(file.original_filename, file.content_type, groups_for(queue, file.kind))
    size = finalize_upload(file.object_key, cap)
    if size is None or not 1 <= size <= cap:
        raise ValidationError({"file_id": "Uploaded attachment is invalid."}, code="invalid_attachment")
    try:
        result, checked = validate_upload(_reader(file, size), extension=extension_from_name(file.original_filename),
                                          group=group, subtype="auto", effective_cap=cap)
    except FormatError as exc:
        raise ValidationError({"file_id": "The file's contents do not match its type.", "code": exc.code},
                              code="invalid_attachment") from exc
    return ServiceObjectValidationResult(size=size, content_type=getattr(result, "mime", "") or checked.canonical_mime)


def attach_job_file(row, *, file_id, actor):
    from apps.machines.service_storage_attach import finalize_file
    return finalize_file(row, file_id=file_id, actor=actor)
