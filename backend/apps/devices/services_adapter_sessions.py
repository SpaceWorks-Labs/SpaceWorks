"""session.start / session.stop / usage.log: an adapter drives the machine-session workflow, never a second one.

``start`` makes the same access decision as ``access.authorize`` and then calls ``machines.sessions_service.start``
(source ``device``), so certification, check-in, booking, lockout, the frozen rate and the monthly session limit are
the ones members and staff already obey. ``stop`` closes only a session THIS adapter started, through
``sessions_service.stop`` (usage entry and charge are raised there, in the charge-tracking ledger). The minutes an
adapter reports are bounded by the session's real elapsed time and its cap (decision 336h): a report that disagrees
with the wall clock bills the bounded wall-clock time and holds the session for staff review. ``usage.log`` is
immutable evidence of what the machine measured; it never edits a session or a charge.
"""
import math
from datetime import datetime, timezone as dt_timezone

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.devices.adapter_access import ACCESS_SWITCH, adapter_device, binding_for, require_adapters
from apps.devices.adapters.caps.session import START, STOP
from apps.devices.adapters.caps.usage_log import LOG
from apps.devices.models import AdapterUsageLog
from apps.devices.services_adapter_access import decide, log_decision, max_seconds, normalise_reason
from apps.devices.services_adapter_core import AdapterError, audit_adapter, check

REF = "adapter:{}"
TOLERANCE_MINUTES = 1  # rounding and clock skew between the adapter's count and the server clock


def start(principal, body):
    check(START, body, label="session start")
    from apps.machines import event_use
    from apps.machines.models import MachineSession
    from apps.machines.sessions_rules import SessionRefused
    from apps.machines.sessions_service import start as start_session
    now = timezone.now()
    with transaction.atomic():
        device = adapter_device(principal, lock=True)
        binding = binding_for(device, body["binding_id"], "session.start")
        require_adapters(device.makerspace_id, ACCESS_SWITCH)
        if binding.target_type != "machine" or binding.machine_id is None:
            raise AdapterError("unsupported_target", "Sessions run on a machine binding.", status_code=409)
        member, machine, reason = decide(device, binding, body["credential"], now)
        session = None
        if reason == "ok":
            try:
                with transaction.atomic():
                    session = start_session(machine, member, actor=None, source=MachineSession.Source.DEVICE, now=now)
                    MachineSession.objects.filter(pk=session.pk).update(device_job_ref=REF.format(device.pk))
                    event_use.attach_quiet(session, body.get("event_id"))
            except SessionRefused as exc:
                reason = normalise_reason(getattr(exc, "code", "machine_unavailable"))
        log_decision(device, binding, body["credential"]["type"], member, reason, now,
                     session_id=session.pk if session else None)
    if session is None:
        return {"allowed": False, "decision": "denied", "reason": reason}
    return {"allowed": True, "decision": "allowed", "reason": "ok", "session_id": session.pk,
            "max_seconds": max_seconds(machine, binding)}


def checked_minutes(device, session, reported, now):
    """``(minutes to bill, flag for review)`` for adapter-reported minutes (``None`` = the wall clock, unflagged).

    Billable time never exceeds the session's elapsed wall-clock minutes or its cap (machine policy, shortened by the
    adapter config) plus the tolerance. Over-reporting beyond that, or reporting well under the wall clock (more than
    10% and the tolerance), bills ``min(elapsed, cap)`` and flags the session, so staff confirm or amend it before any
    charge is final: a compromised or buggy adapter can neither overcharge a member nor give use away.
    """
    if reported is None:
        return None, False
    from apps.devices.models import AdapterBinding
    elapsed = max(round((now - session.started_at).total_seconds() / 60), 0)
    binding = AdapterBinding.objects.filter(device=device, target_type="machine", machine_id=session.machine_id).first()
    cap = math.ceil(max_seconds(session.machine, binding) / 60)
    bounded = min(elapsed, cap)
    ceiling = bounded + TOLERANCE_MINUTES
    floor = elapsed - max(2 * TOLERANCE_MINUTES, math.ceil(elapsed * 0.1))
    if floor <= reported <= ceiling:
        return reported, False
    return bounded, True


def stop(principal, session_id, body):
    check(STOP, body, label="session stop")
    from apps.machines.models import MachineSession
    from apps.machines.sessions_rules import SessionRefused
    from apps.machines.sessions_service import stop as stop_session
    require_adapters(principal.makerspace_id)
    with transaction.atomic():
        device = adapter_device(principal, lock=True)
        session = MachineSession.objects.filter(
            pk=session_id, makerspace_id=device.makerspace_id, source=MachineSession.Source.DEVICE,
            device_job_ref=REF.format(device.pk)).first()
        if session is None:
            raise NotFound()
        reason = MachineSession.StopReason.MEMBER if body.get("reason") == "member" else MachineSession.StopReason.DEVICE
        reported = body.get("active_minutes", 0) + body.get("idle_minutes", 0) if "active_minutes" in body else None
        now = timezone.now()
        minutes, flag = checked_minutes(device, session, reported, now) if session.ended_at is None else (reported, False)
        try:
            session = stop_session(session, actor=None, reason=reason, at=now, minutes=minutes, flag=flag)
        except SessionRefused as exc:
            raise AdapterError(getattr(exc, "code", "session_closed"), "This session has already stopped.",
                               status_code=409) from exc
        meta = {"session_id": session.pk, "reason": reason}
        if flag:
            meta.update(minutes_flagged=True, reported_minutes=reported, billed_minutes=minutes)
        audit_adapter(device.makerspace, device, "devices.adapter_session_stopped", meta=meta)
    return {"session_id": session.pk, "stopped": True, "minutes": session.duration_minutes}


def log_usage(principal, body):
    check(LOG, body, label="usage log")
    with transaction.atomic():
        device = adapter_device(principal, lock=True)
        binding = binding_for(device, body["binding_id"], "usage.log")
        started = datetime.fromtimestamp(body["started_at"], tz=dt_timezone.utc)
        ended = datetime.fromtimestamp(body["ended_at"], tz=dt_timezone.utc)
        if ended < started:
            raise AdapterError("invalid_range", "ended_at is before started_at.")
        try:
            with transaction.atomic():
                row = AdapterUsageLog.objects.create(
                    makerspace=device.makerspace, device=device, binding=binding, operation_id=body["operation_id"],
                    session_id_snapshot=body.get("session_id"), started_at=started, ended_at=ended,
                    active_minutes=body["active_minutes"], idle_minutes=body["idle_minutes"], outcome=body["outcome"],
                    error_code=body.get("error_code", ""), consumptions=body.get("consumptions", []))
        except IntegrityError:
            return {"operation_id": body["operation_id"], "result": "duplicate"}
        audit_adapter(device.makerspace, device, "devices.adapter_usage_logged", meta={
            "binding_id": str(binding.pk), "usage_id": str(row.pk), "outcome": body["outcome"]})
    return {"operation_id": body["operation_id"], "result": "stored"}
