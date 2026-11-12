"""Decision 216 item 4: what a staff booking would meet at admission, shown before submit.

Read-only by construction. Every blocking answer comes from calling the SAME admission seams
`validate_admission` calls (`_refuse_room_outage`, `_refuse_machine_under_repair`,
`_require_certification`) and catching their refusal; no rule is restated here. The
machine access check (decision 319) is the same single function sessions use.

Two facts are advisory, not refusals, because admission does not refuse on them: a WARN-mode
room outage, and a maintenance lockout (`machines.lockout`), which stops jobs and sessions on
the machine at start time but not the booking of its time.

`maintenance_link` names the machine whose repair/lockout record the actor may open. It is
offered only while `machines.maintenance` is on and only to an actor who can manage that
exact machine (`machines.access.can_manage_machine`, which narrows by per-type role scope).
"""

from types import SimpleNamespace

from rest_framework.exceptions import PermissionDenied

from apps.separability.registry import runtime_active

from .exceptions import BookingConflict, MachineUnderRepair

OK, BLOCKED, WARNING = "ok", "blocked", "warning"


def _check(code, state, detail, **extra):
    return {"code": code, "state": state, "detail": detail, **extra}


def _room_outage(space, window):
    from .admission import _refuse_room_outage, room_outages_apply
    if not room_outages_apply(space):
        return None
    try:
        _refuse_room_outage(space, window)
    except BookingConflict as refused:
        return _check("room_outage", BLOCKED, str(refused))
    from apps.maintenance.repairs.room_outages import _overlaps, open_outage
    outage = open_outage(space)
    if outage is not None and _overlaps(outage, window.starts_at, window.ends_at):
        return _check("room_outage", WARNING, "This room has an open outage at that time; bookings are still allowed.")
    return _check("room_outage", OK, "No room outage blocks this time.")


def _time_booking(space):
    from .admission import machine_time_booking_off
    if machine_time_booking_off(space):
        return _check("machine_time_booking", BLOCKED, "Machine time booking is switched off here.")
    return None


def _machine(space):
    from .admission import machine_repairs_apply
    if not machine_repairs_apply(space):
        return None
    from apps.machines.models import Machine
    return Machine.objects.select_related("makerspace", "machine_type").filter(
        pk=space.machine_id, makerspace_id=space.makerspace_id).first()


def _machine_repair(space, window):
    from .admission import _refuse_machine_under_repair
    try:
        _refuse_machine_under_repair(space, window)
    except MachineUnderRepair as refused:
        return _check("machine_repair", BLOCKED, str(refused))
    return _check("machine_repair", OK, "The machine is not under repair at that time.")


def _machine_lockout(machine):
    from apps.machines.lockout import blocking_schedules, lockout_active
    if not lockout_active(machine.makerspace):
        return None
    if blocking_schedules(machine):
        return _check("machine_lockout", WARNING, "Overdue safety maintenance locks this machine: "
                      "the booking is allowed, but the machine cannot be started until it is done.")
    return _check("machine_lockout", OK, "No overdue safety maintenance locks this machine.")


def _machine_access(space, member):
    from .services_bookings import _require_certification
    if member is None or not space.machine_type_id:
        return None
    try:
        _require_certification(space, member, None, "")
    except PermissionDenied as refused:
        detail = refused.detail if isinstance(refused.detail, dict) else {}
        return _check("machine_access", BLOCKED, "The member has no machine access for this booking.",
                      reason=str(detail.get("code", "no_machine_access")))
    return _check("machine_access", OK, "The member has access to this machine.")


def _maintenance_link(actor, machine, checks):
    from apps.makerspaces.platform import feature_enabled
    flagged = {row["code"] for row in checks if row["state"] != OK}
    if machine is None or not flagged & {"machine_repair", "machine_lockout"}:
        return None
    if not runtime_active("maintenance") or not feature_enabled(machine.makerspace, "machines.maintenance"):
        return None
    from apps.machines.access import can_manage_machine
    return {"machine_id": machine.pk} if can_manage_machine(actor, machine) else None


def readiness(space, *, member, starts_at, ends_at, actor):
    """The admission facts for `member` booking `space` over the window, without writing."""
    window = SimpleNamespace(starts_at=starts_at, ends_at=ends_at)
    machine = _machine(space)
    checks = [_time_booking(space), _room_outage(space, window)]
    if machine is not None:
        checks += [_machine_repair(space, window), _machine_lockout(machine)]
    checks.append(_machine_access(space, member))
    checks = [row for row in checks if row is not None]
    return {
        "ready": all(row["state"] != BLOCKED for row in checks),
        "checks": checks,
        "maintenance_link": _maintenance_link(actor, machine, checks),
    }
