"""access.authorize: a credential at an adapter in, an allow/deny decision with a typed reason out.

The decision is made by the EXISTING rules (``machines.sessions_rules.refusal`` for a machine; active, unrestricted
membership for a door or the space). Fail closed: any unexpected error is ``internal_error_fail_closed``. Every
decision, grant or denial, is an append-only ``AdapterAccessLog`` row. A denial never touches a live session.
"""
import logging

from django.db import transaction
from django.utils import timezone

from apps.devices.adapter_access import adapter_device, binding_for
from apps.devices.adapters.caps.access_authorize import REASONS, REQUEST
from apps.devices.models import AdapterAccessLog, AdapterStatus
from apps.devices.services_adapter_core import audit_adapter, check

logger = logging.getLogger(__name__)
CODE_MAP = {"machine_booked": "booked_by_other", "booking_required": "booking_required",
            "maintenance_lockout": "maintenance_lockout", "machine_locked_out": "maintenance_lockout",
            "locked_out": "maintenance_lockout", "supervised_session_closed": "supervision_required"}


def normalise_reason(code):
    code = CODE_MAP.get(code, code)
    return code if code in REASONS else "machine_unavailable"


def resolve_member(makerspace, credential, now, *, binding=None):
    """(member, reason). A card QR needs the member's PIN too; see ``services_adapter_pin`` for the rules."""
    from apps.devices.services_adapter_pin import resolve
    return resolve(makerspace, credential, now, binding=binding)


def _entry_refusal(makerspace, member):
    """A door or the space itself: an active, unrestricted member of this space (no check-in: this IS the entry)."""
    from apps.makerspaces.models import MakerspaceMembership
    if getattr(member, "access_status", "active") != "active" or not member.is_active:
        return "member_restricted"
    if not MakerspaceMembership.objects.filter(makerspace=makerspace, user=member, status="active").exists():
        return "membership_required"
    return None


def _machine_refusal(binding, member, now):
    from apps.machines.sessions_rules import refusal
    from apps.machines.models import Machine
    machine = Machine.objects.select_related("makerspace", "machine_type").filter(
        pk=binding.machine_id, makerspace_id=binding.makerspace_id).first()
    if machine is None:
        return None, "unsupported_target"
    status = AdapterStatus.objects.filter(binding=binding).first()
    from apps.devices.services_adapter_safety import area_blocked
    if area_blocked(binding):
        return machine, "area_not_clear"
    from apps.devices.services_adapter_safety import config_of
    filter_ok = (status.payload.get("interlocks", {}).get("filter_ok") if status is not None else None)
    if filter_ok is False or (filter_ok is None and config_of(binding).get("require_filter_ok")):
        return machine, "filter_alert"
    found = refusal(machine, member, now=now)
    return machine, (normalise_reason(found["code"]) if found else None)


def policy_max_seconds(machine):
    from apps.machines.job_policy import policy_for
    return (policy_for(machine.makerspace, machine.machine_type).session_max_minutes or 240) * 60


def max_seconds(machine, binding=None):
    """The cap told to the adapter: machine policy, shortened by the adapter config when there is one."""
    if binding is None:
        return policy_max_seconds(machine)
    from apps.devices.services_adapter_safety import effective_max_seconds
    return effective_max_seconds(binding, machine)


def decide(device, binding, credential, now):
    """(member, machine, reason) for a credential at a binding; fails closed. Caller holds the device lock."""
    member, reason, machine = None, "ok", None
    try:
        with transaction.atomic():  # a savepoint, so a failure here cannot poison the log write after it
            member, reason = resolve_member(device.makerspace, credential, now, binding=binding)
            if member is not None and binding.target_type == "machine":
                machine, refused = _machine_refusal(binding, member, now)
                reason = refused or "ok"
            elif member is not None and binding.target_type in ("door", "space"):
                reason = _entry_refusal(device.makerspace, member) or "ok"
            elif member is not None:
                reason = "unsupported_target"
    except Exception:  # noqa: BLE001 - fail closed: an unexpected error must never open a door or machine
        logger.warning("adapter access decision failed", exc_info=True)
        member, machine, reason = None, None, "internal_error_fail_closed"
    return member, machine, reason


def log_decision(device, binding, credential_type, member, reason, now, session_id=None):
    allowed = reason == "ok"
    row = AdapterAccessLog.objects.create(
        makerspace=device.makerspace, device=device, binding=binding, member=member, credential_type=credential_type,
        allowed=allowed, reason=reason, session_id_snapshot=session_id, created_at=now)
    audit_adapter(device.makerspace, device, "devices.adapter_access_decided", meta={
        "binding_id": str(binding.pk), "allowed": allowed, "reason": reason, "member_id": getattr(member, "pk", None)})
    from apps.devices.adapter_notifications import on_access
    on_access(row)


def authorize(principal, body):
    check(REQUEST, body, label="access request")
    now = timezone.now()
    with transaction.atomic():
        device = adapter_device(principal, lock=True)
        binding = binding_for(device, body["binding_id"], "access.authorize")
        member, machine, reason = decide(device, binding, body["credential"], now)
        log_decision(device, binding, body["credential"]["type"], member, reason, now)
    allowed = reason == "ok"
    out = {"allowed": allowed, "decision": "allowed" if allowed else "denied", "reason": reason}
    if allowed and machine is not None:
        out["max_seconds"] = max_seconds(machine, binding)
    return out
