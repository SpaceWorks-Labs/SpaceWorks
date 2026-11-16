"""Device sessions (#158.2c): an integrated machine's own job reports open and close one.

Called by the devices agent-report seam (`devices/services_integration_reports.report_job`)
after a report is applied -- never a second device API. A `started` report opens a
session on the device's bound machine for the job's member; `completed`/`failed` close
it with the duration the machine measured. The session is attributed through the job:
its member when that person is an active member of the space, otherwise it is held as
UNATTRIBUTED for staff to assign -- never charged to a guess. Every device session runs an
L12 job, so it is billed through that job only, never twice. A failure stays the job's
staff decision (#142); the session records the time either way.

Inert unless `machines.sessions` is on (and `machines.integrations`, which the report
route already requires). Never raises into the report: a session problem is logged.
"""

import logging

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.audit import services as audit

logger = logging.getLogger(__name__)


def attributed_member(machine, request):
    """The job's member if they are an active community member of this space, else None."""
    from apps.accounts.models import User
    from apps.accounts.staff_identity import person_q
    candidate = request.member_id or request.requester_id
    if candidate is None:
        return None
    return User.objects.filter(
        person_q(), pk=candidate, is_active=True, access_status="active", is_tenant_dump_stub=False,
        retired_at__isnull=True, deletion_requested_at__isnull=True, account_purged_at__isnull=True,
        makerspace_memberships__makerspace_id=machine.makerspace_id, makerspace_memberships__status="active",
    ).first()


def _open(job):
    from apps.machines.models import MachineSession
    request, machine = job.service_request, job.machine
    if MachineSession.objects.filter(service_request=request, source="device").exists():
        return None
    member = attributed_member(machine, request)
    try:
        with transaction.atomic():
            session = MachineSession.objects.create(
                makerspace_id=machine.makerspace_id, machine=machine, machine_type=machine.machine_type,
                member=member, source=MachineSession.Source.DEVICE, started_at=timezone.now(),
                service_request=request, device_job_ref=str(job.pk)[:64])
    except IntegrityError:
        # Someone already holds a live session on this machine; the job still bills itself.
        audit.record(None, "machine_session.device_skipped", makerspace=machine.makerspace, target=machine,
                     meta={"machine_id": machine.pk, "service_request_id": request.pk, "reason": "machine_in_use"})
        return None
    audit.record(None, "machine_session.started", makerspace=machine.makerspace, target=session,
                 meta={"session_id": session.pk, "machine_id": machine.pk, "source": "device", "billable": False,
                       "member_id": getattr(member, "pk", None), "service_request_id": request.pk})
    return session


def _close(job):
    from apps.machines.models import MachineSession
    from apps.machines.sessions_service import stop
    session = MachineSession.objects.filter(service_request_id=job.service_request_id, source="device",
                                            ended_at__isnull=True).first()
    if session is None:
        return None
    return stop(session, actor=None, reason=MachineSession.StopReason.DEVICE, minutes=job.actual_minutes)


def on_agent_report(job, event):
    """The devices seam: `started` opens, `completed`/`failed` close. Fail safe."""
    from apps.machines.sessions_state import sessions_on
    try:
        if job is None or job.service_request_id is None or not sessions_on(job.makerspace):
            return None
        with transaction.atomic():
            return _open(job) if event == "started" else _close(job)
    except Exception:
        logger.exception("machine_session_device_report_failed", extra={"printer_job_id": str(getattr(job, "pk", ""))})
        return None
