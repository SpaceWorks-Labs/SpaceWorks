"""artifact.upload: adapter-uploaded timelapses, job thumbnails/previews, failure snapshots, log bundles, audio clips.

Privacy and storage rules (decision 321b, INVARIANTS on object storage):
- every object is PRIVATE and uploaded through a presigned URL that lands on the STAGING key; ``complete`` promotes it
  to the final key exactly once (``service_storage.finalize_upload``), so a still-valid presign cannot replace a ready file;
- per-kind size cap and retention (``caps.artifact_upload.LIMITS``; days overridable with ``ADAPTER_ARTIFACT_RETENTION_DAYS``);
- the limit key ``adapter_artifacts`` (default none) refuses only the START of a new artifact;
- readable by staff in the machine scope and by the owner of the linked job (never audio or log bundles);
- bytes are deleted at expiry (the row stays as a ``purged`` marker, set only once storage CONFIRMED both keys are
  gone; a failure is logged and retried by the next sweep) and on module purge (``devices_private_keys``);
- a job link must be a job assigned to the binding's own machine, so an adapter cannot attach media to another
  machine's job (L-A2); every signed GET is a download with a fixed type (``presigned_download_url``).
"""
import logging
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.audit import services as audit
from apps.devices.adapter_access import (ARTIFACTS_SWITCH, AUDIO_RECORDING_SWITCH, DIAGNOSTICS_SWITCH, adapter_device,
                                         authorize_staff, binding_for, require_adapters)
from apps.devices.adapters.caps.artifact_upload import KINDS, LIMITS, REQUEST
from apps.devices.models import AdapterArtifact, AdapterCommand, AdapterWatch
from apps.devices.services_adapter_core import AdapterError, audit_adapter, check
from apps.devices.services_locks import lock_tenant
from apps.managed_hosting.extra_quotas import check_extra_quota

CONTENT_TYPES = {
    "timelapse": {"video/mp4", "video/webm"},
    "thumbnail": {"image/jpeg", "image/png", "image/webp"},
    "preview": {"image/jpeg", "image/png", "image/webp"},
    "failure_snapshot": {"image/jpeg", "image/png", "image/webp"},
    "log_bundle": {"application/gzip", "application/zip", "text/plain"},
    "audio_recording": {"audio/ogg", "audio/webm", "audio/mpeg", "audio/wav"},
}
PENDING_HOURS = 2
OWNER_KINDS = ("thumbnail", "preview", "timelapse", "failure_snapshot")
logger = logging.getLogger(__name__)


def retention_days(kind):
    override = getattr(settings, "ADAPTER_ARTIFACT_RETENTION_DAYS", {}) or {}
    return int(override.get(kind, LIMITS[kind][1]))


def _kind_gate(makerspace_id, kind):
    require_adapters(makerspace_id, ARTIFACTS_SWITCH)
    if kind == "audio_recording":
        require_adapters(makerspace_id, AUDIO_RECORDING_SWITCH)
    if kind == "log_bundle":
        require_adapters(makerspace_id, DIAGNOSTICS_SWITCH)


def _validate_links(device, binding, body):
    if body["kind"] == "log_bundle":
        command = AdapterCommand.objects.filter(
            pk=body.get("command_id"), binding=binding, capability="diagnostics", command="log_bundle",
            status__in=(AdapterCommand.Status.LEASED, AdapterCommand.Status.SUCCEEDED)).first()
        if command is None or AdapterArtifact.objects.filter(command_id=command.pk).exists():
            raise AdapterError("log_bundle_not_requested", "No open log bundle request matches.", status_code=409)
    if body["kind"] == "audio_recording":
        watch = AdapterWatch.objects.filter(binding=binding, status=AdapterWatch.Status.ACTIVE, audio=True, record=True,
                                            audio_notice_ack=True, expires_at__gt=timezone.now()).exists()
        if not watch:
            raise AdapterError("audio_recording_not_consented", "Audio is recorded only during a watch whose notice "
                               "was acknowledged.", status_code=409)
    request_id = body.get("service_request_id")
    if request_id is not None:
        from apps.machines.models import MachineServiceRequest
        # The job must run on THIS binding's machine; a door/space binding links no job. One 404 for all misses.
        if binding.machine_id is None or not MachineServiceRequest.objects.filter(
                pk=request_id, makerspace_id=device.makerspace_id, assigned_machine_id=binding.machine_id).exists():
            raise AdapterError("invalid_link", "That job is not assigned to this binding's machine.", status_code=404)


def _upload(row):
    from apps.evidence.storage import StorageUnavailable
    from apps.machines.service_storage import presigned_upload
    try:
        upload = presigned_upload(row.object_key, row.content_type, LIMITS[row.kind][0])
    except StorageUnavailable as exc:
        raise AdapterError("storage_unavailable", "Storage is unavailable; retry.", status_code=503) from exc
    return {"artifact_id": str(row.pk), "object_key": row.object_key, "upload": upload,
            "expires_at": int(row.expires_at.timestamp())}


def request_upload(principal, body):
    check(REQUEST, body, label="artifact request")
    kind = body["kind"]
    cap, _days = LIMITS[kind]
    if body["size_bytes"] > cap:
        raise AdapterError("artifact_too_large", "The artifact is larger than this kind allows.", status_code=413,
                           max_bytes=cap)
    if body["content_type"] not in CONTENT_TYPES[kind]:
        raise AdapterError("content_type_not_allowed", "That content type is not allowed for this kind.")
    now = timezone.now()
    with transaction.atomic():
        device = adapter_device(principal, lock=True)
        binding = binding_for(device, body["binding_id"], "artifact.upload")
        _kind_gate(device.makerspace_id, kind)
        existing = AdapterArtifact.objects.select_for_update().filter(
            binding=binding, operation_id=body["operation_id"]).first()
        if existing is not None:
            if existing.status != AdapterArtifact.Status.PENDING:
                return {"artifact_id": str(existing.pk), "status": existing.status, "duplicate": True}
            return {**_upload(existing), "duplicate": True}
        _validate_links(device, binding, body)
        makerspace = lock_tenant(device.makerspace_id)
        check_extra_quota(makerspace, "adapter_artifacts")
        check_extra_quota(makerspace, "adapter_media_bytes", adding=int(body["size_bytes"]))  # decision 328a
        row = AdapterArtifact.objects.create(
            makerspace=makerspace, binding=binding, operation_id=body["operation_id"], kind=kind,
            content_type=body["content_type"], size_bytes=body["size_bytes"],
            object_key=f"adapter-artifacts/{makerspace.pk}/{binding.pk}/{uuid.uuid4().hex}",
            service_request_id=body.get("service_request_id"), session_id=body.get("session_id"),
            command_id=body.get("command_id"), expires_at=now + timedelta(days=retention_days(kind)),
            captured_at=now)
        audit_adapter(makerspace, device, "devices.adapter_artifact_requested", meta={
            "binding_id": str(binding.pk), "artifact_id": str(row.pk), "kind": kind, "size_bytes": row.size_bytes})
        return _upload(row)


def complete(principal, artifact_id):
    from apps.evidence.storage import StorageUnavailable
    from apps.machines import service_storage
    with transaction.atomic():
        device = adapter_device(principal, lock=True)
        row = AdapterArtifact.objects.select_for_update().select_related("binding").filter(
            pk=artifact_id, binding__device=device, makerspace_id=device.makerspace_id).first()
        if row is None:
            raise NotFound()
        require_adapters(device.makerspace_id, ARTIFACTS_SWITCH)
        if row.status == AdapterArtifact.Status.READY:
            return {"artifact_id": str(row.pk), "status": row.status}
        if row.status != AdapterArtifact.Status.PENDING:
            raise AdapterError("artifact_expired", "This artifact is no longer available.", status_code=410)
        try:
            size = service_storage.finalize_upload(row.object_key, LIMITS[row.kind][0])
        except StorageUnavailable as exc:
            raise AdapterError("storage_unavailable", "Storage is unavailable; retry.", status_code=503) from exc
        if size is None:
            raise AdapterError("upload_missing", "The file has not been uploaded yet.", status_code=409)
        if size > LIMITS[row.kind][0]:
            service_storage.cleanup_upload(row.object_key)
            AdapterArtifact.objects.filter(pk=row.pk).update(status=AdapterArtifact.Status.PURGED,
                                                             purged_at=timezone.now())
            raise AdapterError("artifact_too_large", "The uploaded file is too large.", status_code=413)
        AdapterArtifact.objects.filter(pk=row.pk).update(
            status=AdapterArtifact.Status.READY, completed_at=timezone.now(), size_bytes=size)
        audit_adapter(device.makerspace, device, "devices.adapter_artifact_stored", meta={
            "binding_id": str(row.binding_id), "artifact_id": str(row.pk), "kind": row.kind, "size_bytes": size})
    return {"artifact_id": str(row.pk), "status": "ready"}


def serialize(row):
    return {"id": str(row.pk), "binding_id": str(row.binding_id), "kind": row.kind, "content_type": row.content_type,
            "size_bytes": row.size_bytes, "status": row.status, "service_request_id": row.service_request_id,
            "session_id": row.session_id, "created_at": row.created_at, "expires_at": row.expires_at}


def _hide_unswitched(queryset, makerspace_id):
    """Kinds whose child switch is off are not listed (audio and bundles have their own switches)."""
    from apps.devices.adapter_access import adapters_enabled
    if not adapters_enabled(makerspace_id, AUDIO_RECORDING_SWITCH):
        queryset = queryset.exclude(kind="audio_recording")
    if not adapters_enabled(makerspace_id, DIAGNOSTICS_SWITCH):
        queryset = queryset.exclude(kind="log_bundle")
    return queryset


def staff_list(actor, binding, params):
    from apps.devices.adapter_access import scoped_binding
    binding = scoped_binding(actor, binding, child=ARTIFACTS_SWITCH)
    queryset = _hide_unswitched(AdapterArtifact.objects.filter(binding=binding).exclude(
        status=AdapterArtifact.Status.PENDING), binding.makerspace_id)
    if params.get("kind") in KINDS:
        queryset = queryset.filter(kind=params["kind"])
    if str(params.get("service_request_id", "")).isdigit():
        queryset = queryset.filter(service_request_id=int(params["service_request_id"]))
    return queryset


def _signed(row):
    from apps.evidence.storage import StorageUnavailable
    from apps.machines.service_storage import presigned_download_url
    try:
        return {"url": presigned_download_url(row.object_key, row.content_type), "content_type": row.content_type,
                "kind": row.kind}
    except StorageUnavailable as exc:
        raise AdapterError("storage_unavailable", "Storage is unavailable; retry.", status_code=503) from exc


def staff_url(actor, artifact_id):
    from apps.devices.adapter_access import scoped_binding
    row = AdapterArtifact.objects.select_related("binding").filter(pk=artifact_id).first()
    if row is None:
        raise NotFound()
    scoped_binding(actor, row.binding_id, child=ARTIFACTS_SWITCH)
    visible = _hide_unswitched(AdapterArtifact.objects.filter(pk=row.pk), row.makerspace_id).exists()
    if not visible or row.status != AdapterArtifact.Status.READY:
        raise NotFound()
    if row.kind in ("audio_recording", "log_bundle"):
        audit.record(actor, "devices.adapter_artifact_viewed", makerspace=row.makerspace, target=row.binding.device,
                     meta={"device_id": str(row.binding.device_id), "artifact_id": str(row.pk), "kind": row.kind})
    return _signed(row)


def _owned_request(actor, request_id):
    from apps.machines.models import MachineServiceRequest
    request = MachineServiceRequest.objects.filter(pk=request_id).first()
    if request is None or (request.member_id or request.requester_id) != actor.pk:
        raise NotFound()
    require_adapters(request.makerspace_id, ARTIFACTS_SWITCH)
    return request


def _owner_rows(request):
    """READY owner-visible artifacts of the job, captured on the job's own machine (a link made before L-A2 to
    another machine's job is not served)."""
    return AdapterArtifact.objects.filter(
        makerspace_id=request.makerspace_id, service_request_id=request.pk, kind__in=OWNER_KINDS,
        status=AdapterArtifact.Status.READY, binding__machine_id=request.assigned_machine_id)


def owner_list(actor, request_id):
    """The job owner sees the artifacts of THEIR job (never audio, never log bundles)."""
    return _owner_rows(_owned_request(actor, request_id))


def owner_url(actor, artifact_id):
    row = AdapterArtifact.objects.filter(pk=artifact_id, kind__in=OWNER_KINDS, status=AdapterArtifact.Status.READY,
                                         service_request_id__isnull=False).first()
    if row is None or not _owner_rows(_owned_request(actor, row.service_request_id)).filter(pk=row.pk).exists():
        raise NotFound()
    return _signed(row)


def _delete_bytes(row):
    """Both keys, every version, CONFIRMED; raises so the row is not marked purged over surviving bytes (L-A5)."""
    from apps.machines.service_storage import purge_upload
    purge_upload(row.object_key)


def due_artifacts(now):
    from django.db.models import Q
    return AdapterArtifact.objects.exclude(status=AdapterArtifact.Status.PURGED).filter(
        Q(expires_at__lte=now) | Q(status=AdapterArtifact.Status.PENDING,
                                   created_at__lte=now - timedelta(hours=PENDING_HOURS)))


def purge_expired(now=None, space_id=None):
    """Delete bytes past retention and abandoned uploads (idempotent). The row stays as a purged marker."""
    now = now or timezone.now()
    stale = now - timedelta(hours=PENDING_HOURS)
    scope = AdapterArtifact.objects.filter(makerspace_id=space_id) if space_id else AdapterArtifact.objects
    rows = scope.exclude(status=AdapterArtifact.Status.PURGED).filter(expires_at__lte=now)[:200]
    pending = scope.filter(status=AdapterArtifact.Status.PENDING, created_at__lte=stale)[:200]
    done = 0
    for row in [*rows, *pending]:
        try:
            _delete_bytes(row)
        except Exception:  # noqa: BLE001 - logged and left due: the next sweep retries
            logger.warning("adapter_artifact_purge_failed", extra={"artifact_id": str(row.pk)}, exc_info=True)
            continue
        AdapterArtifact.objects.filter(pk=row.pk).update(status=AdapterArtifact.Status.PURGED, purged_at=now)
        audit.record(None, "devices.adapter_artifact_purged", makerspace=row.makerspace, target=row.binding,
                     meta={"artifact_id": str(row.pk), "kind": row.kind})
        done += 1
    return done

