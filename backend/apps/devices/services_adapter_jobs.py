"""job.dispatch / file.fetch: an adapter leases a machine-service job and reports it through the SAME workflow.

There is no second job state machine. The run record is the existing ``PrinterJob`` (one row per dispatch) with
its ``DeviceCommand`` (kind ``adapter_job``) for lease/ack, and the existing ``printer_access.live_target`` /
``owned_job`` (generalised to an adapter ``Device`` whose machine binding serves ``job.dispatch``). The terminal
report is the printer ``claim_result`` + ``apply_report`` path: idempotent by operation id, measured consumption
only, and it lands in staff review (an adapter binding never auto-applies). Legacy printer routes are untouched.
"""
import uuid
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils.translation import gettext
from rest_framework.exceptions import NotFound, ValidationError

from apps.audit import services as audit
from apps.devices import services_commands as delivery
from apps.devices.adapter_access import adapter_device, require_adapters, scoped_binding
from apps.devices.adapters.caps.job_dispatch import ACK, PROGRESS, REPORT
from apps.devices.models import AdapterBinding, Device, DeviceCommand, PrinterJob
from apps.devices.printer_access import lock_printer_tenant, live_target, owned_job, target_binding
from apps.devices.services_adapter_core import AdapterError, check
from apps.devices.services_printer_apply import report_result
from apps.devices.services_printer_events import record
from apps.devices.services_printer_reports import telemetry
from apps.machines.models import Machine, MachineServiceRequest

KIND = "adapter_job"
PENDING = "pending-"
TWO = Decimal("0.01")


def create_job(actor, binding_id, service_request_id):
    """Staff dispatch an in-progress request, assigned to the bound machine, to its adapter (audited, scoped)."""
    # Tenant-scoped lookup first: a foreign or missing binding is the same 404, never a 403 oracle (L-A6).
    binding = scoped_binding(actor, binding_id)
    if binding.machine_id is None or "job.dispatch" not in binding.capabilities or not binding.enabled:
        raise AdapterError("capability_missing", "This binding does not serve job dispatch.", status_code=409)
    try:
        with transaction.atomic():
            makerspace = lock_printer_tenant(binding.makerspace_id)
            device = Device.objects.select_for_update().get(pk=binding.device_id)
            request = MachineServiceRequest.objects.select_for_update().filter(
                pk=service_request_id, makerspace=makerspace).first()
            if (request is None or request.status != MachineServiceRequest.Status.IN_PROGRESS
                    or request.assigned_machine_id != binding.machine_id):
                raise ValidationError(gettext("An in-progress request assigned to this machine is required."))
            machine = Machine.objects.select_for_update().filter(
                pk=binding.machine_id, makerspace=makerspace, is_active=True).first()
            if machine is None or device.status != Device.Status.ACTIVE or device.kind != Device.Kind.ADAPTER:
                raise AdapterError("adapter_unavailable", "The adapter or machine is not available.", status_code=409)
            command = DeviceCommand.objects.create(makerspace=makerspace, device=device, kind=KIND,
                                                   device_key_version=device.key_version, created_by=actor)
            job = PrinterJob.objects.create(
                command=command, makerspace=makerspace, device=device, machine=machine, service_request=request,
                machine_id_snapshot=machine.pk, machine_name=machine.name, service_request_id_snapshot=request.pk,
                service_request_name=f"Request {request.pk}", external_job_id=f"{PENDING}{uuid.uuid4().hex}")
            record(makerspace, device, "printer_job_created", actor=actor, job=job, command=command)
            from apps.devices.services_adapter_webhook import wake
            wake(device, "job.queued", binding_id=binding.pk, capability="job.dispatch")
            return job
    except IntegrityError as exc:
        raise AdapterError("job_exists", "This request already has a live dispatched job.", status_code=409) from exc


def _own_job(principal, job_id):
    """(job, command) of THIS adapter, else 404; the caller holds the device lock."""
    require_adapters(principal.makerspace_id)
    device = adapter_device(principal, lock=True)
    job, command = owned_job(device, job_id)
    return device, job, command


def lease(principal):
    """The next dispatchable job for this adapter (area-clear gate and bounded attempts live in the delivery)."""
    require_adapters(principal.makerspace_id)
    adapter_device(principal)
    payload = delivery.lease_command(principal, kinds=(KIND,))
    if payload is None:
        return {"job": None}
    job = PrinterJob.objects.select_related("service_request").get(pk=payload["printer_job_id"])
    return {"job": {
        "job_id": str(job.pk), "lease_token": payload["lease_token"],
        "lease_expires_at": int(payload["lease_expires_at"].timestamp()),
        "binding_id": str(AdapterBinding.objects.filter(device_id=job.device_id, machine_id=job.machine_id,
                                                        enabled=True).values_list("pk", flat=True).first() or ""),
        "machine_id": job.machine_id, "service_request_id": job.service_request_id,
        "has_files": job.service_request.files.filter(attached_at__isnull=False).exists() if job.service_request else False}}


def acknowledge(principal, job_id, body):
    """Ack the lease and bind the vendor's own job id (``external_job_id``) to the run; idempotent."""
    check(ACK, body, label="job ack")
    if body["external_job_id"].startswith(PENDING):  # our own placeholder prefix: the DB guard would answer a 500
        raise AdapterError("external_job_id_reserved", "External job ids may not start with 'pending-'.",
                           status_code=400)
    require_adapters(principal.makerspace_id)
    adapter_device(principal)
    identity = PrinterJob.objects.filter(pk=job_id, device_id=principal.device_id,
                                         makerspace_id=principal.makerspace_id).values("command_id").first()
    if identity is None:
        raise NotFound()
    delivery.acknowledge(principal, identity["command_id"], body["lease_token"])
    with transaction.atomic():
        device, job, _command = _own_job(principal, job_id)
        wanted = body["external_job_id"]
        if job.external_job_id.startswith(PENDING):
            try:
                with transaction.atomic():
                    job.external_job_id = wanted
                    job.save(update_fields=["external_job_id"])
            except IntegrityError as exc:
                raise AdapterError("external_job_in_use", "That external job id is already used.",
                                   status_code=409) from exc
        elif job.external_job_id != wanted:
            raise AdapterError("external_job_mismatch", "The job is already bound to another external id.",
                               status_code=409)
    return {"job_id": str(job_id), "status": "acknowledged"}


def progress(principal, job_id, body):
    check(PROGRESS, body, label="job progress")
    adapter_device(principal)  # 404 while machines.integrations is off, 403 once revoked: before any job lookup
    job = PrinterJob.objects.filter(pk=job_id, device_id=principal.device_id,
                                    makerspace_id=principal.makerspace_id).first()
    if job is None:
        raise NotFound()
    telemetry(principal, job_id, {"external_job_id": job.external_job_id, "telemetry_state": "running",
                                  "progress_percent": int(body.get("progress_percent", job.progress_percent or 0))})
    return {"job_id": str(job_id), "result": "stored"}


def _money(value):
    return None if value is None else Decimal(str(value)).quantize(TWO)


def _result(job, body):
    """The adapter's report in the printer protocol's strict shape; measured values only, never money."""
    failed = body["outcome"] == "failed"
    return {
        "operation_id": body["operation_id"], "external_job_id": job.external_job_id, "outcome": body["outcome"],
        "actual_minutes": body["actual_minutes"],
        "consumptions": [{"machine_consumable_id": row["machine_consumable_id"], "quantity": _money(row["quantity"])}
                         for row in body["consumptions"]],
        "failure_reason": (body.get("failure_reason") or body.get("error_code") or "failed") if failed else "",
        "percent_complete": (body.get("percent_complete") or 0) if failed else None,
        "actual_grams": _money(body.get("actual_grams")), "actual_quantity": _money(body.get("actual_quantity"))}


def _record_profile(principal, job, entries):
    """Decision 341: measured use by the type's profile key, recorded BEFORE the report applies so an
    auto-applied completion prices it. Measurements only; the device is provenance, never the actor."""
    if not entries or job.service_request_id is None:
        return
    from apps.machines.consumable_usage import record_actuals
    try:
        record_actuals(job.service_request, None, entries, source="adapter", device_ref=str(principal.device_id))
    except ValidationError as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        first = lambda value: value[0] if isinstance(value, list) and value else value  # noqa: E731
        code = str(first(detail.get("code")) or "invalid_profile_consumption")
        message = first(detail.get("consumables")) or "Invalid profile consumption."
        raise AdapterError(_PROFILE_CODES.get(code, "invalid_profile_consumption"), str(message),
                           status_code=409 if code == "consumable_already_recorded" else 400) from exc


_PROFILE_CODES = {"unknown_consumable_key": "unknown_consumable_key",
                  "consumable_already_recorded": "consumable_already_recorded",
                  "consumable_recorder_not_allowed": "consumable_recorder_not_allowed"}


def report(principal, job_id, body):
    """Terminal report: claim then apply through the printer path; identical replays are no-ops, others conflict."""
    check(REPORT, body, label="job report")
    adapter_device(principal)  # same gate as lease/ack/file: a switched-off space accepts no terminal report
    job = PrinterJob.objects.filter(pk=job_id, device_id=principal.device_id,
                                    makerspace_id=principal.makerspace_id).first()
    if job is None:
        raise NotFound()
    if job.external_job_id.startswith(PENDING):
        raise AdapterError("job_not_acknowledged", "Acknowledge the job before reporting it.", status_code=409)
    _record_profile(principal, job, body.get("profile_consumptions") or [])
    # Only a clean (completed) report may auto-apply; a failure always goes to staff review.
    done = report_result(principal, job_id, _result(job, body), hold=body["outcome"] != "completed")
    if done.state == "needs_review":
        from apps.devices.adapter_notifications import notify_job_review
        notify_job_review(done, body["outcome"])
    return {"job_id": str(job_id), "state": done.state, "operation_id": body["operation_id"]}


def files(principal, job_id):
    """Short-lived signed URLs for the job's attached files; only while this adapter holds the acknowledged job."""
    from apps.machines.service_storage import presigned_get_url
    from apps.evidence.storage import StorageUnavailable
    with transaction.atomic():
        device, job, command = _own_job(principal, job_id)
        if command.status != DeviceCommand.Status.ACKNOWLEDGED or job.state != PrinterJob.State.AWAITING:
            raise AdapterError("job_not_active", "Files are served only for a live, acknowledged job.", status_code=409)
        live_target(job, device)
        rows = list(job.service_request.files.filter(attached_at__isnull=False).exclude(
            kind__in=("estimate", "preview", "screenshot")).order_by("created_at"))
        try:
            out = [{"file_id": row.pk, "name": row.original_filename, "content_type": row.content_type,
                    "size_bytes": row.size_bytes, "kind": row.kind, "url": presigned_get_url(row.object_key)}
                   for row in rows]
        except StorageUnavailable as exc:
            raise AdapterError("storage_unavailable", "File storage is unavailable; retry.", status_code=503) from exc
        audit.record(None, "devices.adapter_job_file_fetched", makerspace=device.makerspace, target=job, meta={
            "device_id": str(device.pk), "job_id": str(job.pk), "files": [row.pk for row in rows]})
    return {"job_id": str(job_id), "files": out}
