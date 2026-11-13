"""Attach a staged machine-service file to its request, or delete a staged one.

Split out of `service_storage` (300-line ceiling). Storage helpers are read through the
`service_storage` module at call time, so tests and callers that patch them there keep
working.
"""

from django.utils.translation import gettext
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit
from apps.machines import service_storage as base
from apps.machines.models import MachineServiceRequest, ServiceRequestFile
from apps.makerspaces import limits


def finalize_file(service_request, *, file_id, actor):
    try:
        file = ServiceRequestFile.objects.select_related(
            "makerspace", "machine__makerspace", "queue__makerspace"
        ).get(pk=file_id, owner_user_id=actor.pk)
    except ServiceRequestFile.DoesNotExist as exc:
        raise ValidationError(
            {"file_id": gettext("Attachment is unavailable for this request.")},
            code="invalid_attachment",
        ) from exc
    # Refuse an already-attached file before touching object storage so a retry or
    # concurrent finalize can never delete the live object a committed record points at.
    if file.service_request_id is not None or file.attached_at is not None:
        raise ValidationError({"file_id": gettext("Attachment is unavailable for this request.")}, code="invalid_attachment")
    try:
        result = _validated(file)
        with transaction.atomic():
            locked_request = MachineServiceRequest.objects.select_for_update(of=("self",)).select_related(
                "bucket__machine__makerspace", "queue__makerspace"
            ).get(pk=service_request.pk)
            locked_file = ServiceRequestFile.objects.select_for_update().get(pk=file.pk)
            if (
                locked_file.owner_user_id != actor.pk
                or locked_file.service_request_id is not None
                or locked_file.makerspace_id != locked_request.makerspace_id
                or (locked_request.queue_id and locked_file.queue_id != locked_request.queue_id)
                or (locked_request.bucket_id and locked_file.machine_id != locked_request.bucket.machine_id)
            ):
                raise ValidationError({"file_id": gettext("Attachment is unavailable for this request.")}, code="invalid_attachment")
            limits.charge_upload(locked_request.makerspace, result.size)
            locked_file.service_request = locked_request
            locked_file.attached_at = timezone.now()
            locked_file.size_bytes = result.size
            locked_file.content_type = result.content_type
            locked_file.save(update_fields=["service_request", "attached_at", "size_bytes", "content_type"])
            audit.record(
                actor, "machine_service.file_attached", makerspace=locked_request.makerspace,
                target=locked_file, meta={"request_id": locked_request.pk, "file_id": locked_file.pk, "size_bytes": result.size},
            )
            return locked_file
    except Exception:
        # Only compensate a still-staged upload; if a concurrent finalize won the
        # race and attached this file, leave its object intact.
        if ServiceRequestFile.objects.filter(
            pk=file.pk, service_request__isnull=True, attached_at__isnull=True
        ).exists():
            base.cleanup_upload(file.object_key)
        raise


def _validated(file):
    """Size and content checks: the job flow's maker_formats files, else the legacy policy."""
    from apps.machines.job_files import POLICY_NAME, validate_job_object
    if file.file_policy_name == POLICY_NAME:
        return validate_job_object(file)
    policy = base.policy_for_file(file)
    size = base.finalize_upload(file.object_key, policy.max_bytes)
    if size is None or not 1 <= size <= policy.max_bytes:
        raise ValidationError({"file_id": gettext("Uploaded attachment is invalid.")}, code="invalid_attachment")
    return base.validate_service_object(file, policy)


def delete_staged_file(file, *, actor):
    with transaction.atomic():
        locked = ServiceRequestFile.objects.select_for_update().select_related("makerspace").get(pk=file.pk)
        if locked.service_request_id is not None or locked.attached_at is not None:
            raise ValidationError({"file_id": gettext("Attached files cannot be deleted.")}, code="invalid_attachment")
        audit.record(
            actor, "machine_service.file_deleted", makerspace=locked.makerspace,
            target=locked, meta={"file_id": locked.pk, "size_bytes": locked.size_bytes},
        )
        limits.free_storage(locked.makerspace, locked.size_bytes)
        object_key = locked.object_key
        locked.delete()
    base.cleanup_upload(object_key)
