"""Queue pull and job reports for an integrated printer (release 2 L10, #76).

SpaceWorks stays the system of record. The queue is read-only. A report changes a
machine-service request only through the existing printer adapter, which calls the
machine-service workflow (``service_workflow_actions.complete``/``fail``) and its cost
seam (``record_service_cost``):

* ``started`` attaches this device to a request a staff member already STARTED on the
  device's bound machine (starting picks the material pool, a staff decision). It
  creates the acknowledged printer job the terminal report needs. Repeating it is a no-op.
* ``completed``/``failed`` are the existing immutable terminal report. Repeating the same
  operation is a no-op; a changed one conflicts. A failure is always held for staff
  review (``needs_review``) whatever the binding's auto-apply policy; a completion
  follows the binding's ``auto_apply_terminal`` (off by default, so staff apply it).
"""
from django.utils.translation import gettext
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.audit import services as audit
from apps.devices.errors_integrations import IntegrationConflict
from apps.devices.integration_access import device_binding, require_integrations
from apps.devices.models import Device, DeviceCommand, PrinterJob
from apps.devices.printer_access import locked_device
from apps.devices.services_printer_apply import apply_report
from apps.devices.services_printer_events import record
from apps.devices.services_printer_reports import claim_result
from apps.machines.models import MachineServiceRequest

QUEUE_LIMIT = 50
LIVE_STATES = ("awaiting", "reported", "needs_review")
Status = MachineServiceRequest.Status


def job_queue(principal):
    device = Device.objects.get(pk=principal.device_id, makerspace_id=principal.makerspace_id)
    binding, machine, integration = device_binding(device)
    same_type = Q(queue__machine_type_id=machine.machine_type_id) | Q(bucket__machine_id=machine.pk)
    rows = MachineServiceRequest.objects.filter(makerspace_id=device.makerspace_id).filter(
        Q(status=Status.ACCEPTED) & same_type | Q(status=Status.IN_PROGRESS, assigned_machine_id=machine.pk),
    ).order_by("accepted_at", "pk")[:QUEUE_LIMIT]
    jobs = {row.service_request_id: row.pk for row in PrinterJob.objects.filter(
        device=device, state__in=LIVE_STATES, service_request_id__in=[row.pk for row in rows])}
    return {
        "machine_id": machine.pk, "machine_type_id": machine.machine_type_id,
        "integration_kind": integration.kind, "config_schema_version": integration.config_schema_version,
        "jobs": [{
            "service_request_id": row.pk, "status": row.status,
            "on_this_machine": row.assigned_machine_id == machine.pk,
            "estimated_minutes": row.estimated_minutes, "planned_grams": row.planned_grams,
            "accepted_at": row.accepted_at, "started_at": row.started_at,
            "printer_job_id": jobs.get(row.pk),
        } for row in rows],
    }


def report_job(principal, request_id, serializer):
    require_integrations(principal.makerspace_id)
    data = serializer.validated_data
    try:
        if data["event"] == "started":
            job = _attach(principal, request_id, data["external_job_id"])
        else:
            job = _terminal(principal, request_id, serializer)
    except Exception as exc:
        _audit_refused(principal, request_id, data["event"], getattr(exc, "default_code", "refused"))
        raise
    _audit_applied(principal, request_id, data["event"], job)
    # Lane L23: the same report opens or closes the machine's device session (inert
    # unless `machines.sessions` is on; never raises into the report).
    from apps.machines.sessions_device import on_agent_report
    on_agent_report(job, data["event"])
    return job


def _attach(principal, request_id, external_job_id):
    try:
        with transaction.atomic():
            makerspace, device = locked_device(principal)
            device_binding(device)  # 404 before any request lock when not integrated
            # Lock order of the printer adapter and the workflow: request -> machine -> binding.
            request = MachineServiceRequest.objects.select_for_update(no_key=True).filter(
                pk=request_id, makerspace=makerspace).first()
            if request is None:
                raise IntegrationConflict(gettext("This job is not in the device's queue."), code="job_unknown")
            _binding, machine, _integration = device_binding(device, lock=True)
            live = PrinterJob.objects.filter(service_request=request, state__in=LIVE_STATES).first()
            if live is not None:
                if live.device_id == device.pk and live.external_job_id == external_job_id:
                    return live
                raise IntegrationConflict(gettext("This job already has a different printer run."), code="job_conflict")
            if request.status != Status.IN_PROGRESS or request.assigned_machine_id != machine.pk:
                raise IntegrationConflict(gettext("Staff must start this job on the device's machine first."),
                                          code="job_not_started")
            now = timezone.now()
            command = DeviceCommand.objects.create(
                makerspace=makerspace, device=device, device_key_version=device.key_version,
                status=DeviceCommand.Status.ACKNOWLEDGED, acknowledged_at=now)
            job = PrinterJob.objects.create(
                command=command, makerspace=makerspace, device=device, machine=machine, service_request=request,
                machine_id_snapshot=machine.pk, machine_name=machine.name, service_request_id_snapshot=request.pk,
                service_request_name=f"Request {request.pk}", external_job_id=external_job_id)
            record(makerspace, device, "printer_job_created", job=job, command=command, outcome="agent_started")
            return job
    except IntegrityError as exc:
        raise IntegrationConflict(gettext("This run identity is already used."), code="job_conflict") from exc


def _terminal(principal, request_id, serializer):
    device = Device.objects.get(pk=principal.device_id, makerspace_id=principal.makerspace_id)
    device_binding(device)
    data = serializer.validated_data
    job = PrinterJob.objects.filter(device=device, service_request_id=request_id,
                                    external_job_id=data["external_job_id"]).first()
    if job is None:
        raise IntegrationConflict(gettext("Report the start of this job first."), code="job_not_reported_started")
    job, _claimed = claim_result(principal, job.pk, serializer.result_payload(), hold=data["event"] == "failed")
    if job.state == "reported":
        return apply_report(principal, job.pk)
    return job


def _audit_applied(principal, request_id, event, job):
    audit.record(None, "machine_service.agent_report_applied", makerspace=job.makerspace, target=job, meta={
        "device_id": str(principal.device_id), "service_request_id": int(request_id), "event": event,
        "printer_job_id": str(job.pk), "job_state": job.state})


def _audit_refused(principal, request_id, event, code):
    from apps.makerspaces.models import Makerspace
    makerspace = Makerspace.objects.filter(pk=principal.makerspace_id).first()
    if makerspace is not None:
        audit.record(None, "machine_service.agent_report_refused", makerspace=makerspace, meta={
            "device_id": str(principal.device_id), "service_request_id": int(request_id), "event": event,
            "code": str(code)[:48]})
