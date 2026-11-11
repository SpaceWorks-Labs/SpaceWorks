"""Who may start a machine session, and why not (#158.3).

Every refusal is a typed code, checked in this order: the person (account standing,
membership and waiver, check-in, certification), then the machine (down or under
maintenance, maintenance lockout, someone else's booking, already in use). Staff
starting a session for a member go through exactly the same checks: staff may correct a
session's time afterwards, never override certification or check-in.
"""

from django.utils import timezone
from rest_framework.exceptions import APIException

DOWN = ("maintenance", "offline")
CERTIFICATIONS = "machines.certifications"


class SessionRefused(APIException):
    status_code = 409
    default_code = "session_refused"

    def __init__(self, code, detail, *, status_code=409, **extra):
        super().__init__({"detail": detail, "code": code, **extra}, code)
        self.status_code = status_code
        self.code = code


def _person(machine, member):
    from apps.presence.guard import MemberPresenceRequired, PresenceRequired, WaiverAcceptanceRequired
    from apps.presence.guest_guard import require_member_or_guest
    if member is None or getattr(member, "access_status", "active") != "active" or not member.is_active:
        raise SessionRefused("member_restricted", "This account is restricted or suspended, so it cannot "
                             "start a machine session.", status_code=403)
    from apps.makerspaces.minors_guard import require_minor_clearance  # decision 223 (k)
    require_minor_clearance(member, machine.makerspace, "machine")
    try:
        active = require_member_or_guest(member, machine.makerspace)
        if active.guest_pass is not None:  # decision 223 (d): the pass's machine mode decides
            from apps.machines.guest_access import require_guest_machine
            require_guest_machine(active.guest_pass, member, machine.makerspace, machine=machine)
    except WaiverAcceptanceRequired:
        raise SessionRefused("waiver_acceptance_required", "Accept the space's current waiver first.",
                             status_code=403)
    except PresenceRequired:
        raise SessionRefused("presence_required", "Check in at the space before starting a machine.")
    except MemberPresenceRequired:
        raise SessionRefused("membership_required", "Only active members of this space can use its machines.",
                             status_code=403)


def _is_member(machine, member):
    from apps.makerspaces.models import MakerspaceMembership
    return MakerspaceMembership.objects.filter(
        makerspace_id=machine.makerspace_id, user=member, status="active").exists()


def missing_certifications(machine, member, now=None):
    """Names of the type's required certifications the member lacks (fails closed)."""
    from apps.machines.certifications import active_grant, required_types
    from apps.makerspaces.models import MakerspaceMembership
    from apps.makerspaces.platform import feature_enabled
    if not feature_enabled(machine.makerspace, CERTIFICATIONS):
        return []
    # A session is the member operating the machine themself: any requirement the type
    # sets, for a job or for booking time, applies.
    required = list(required_types(machine.makerspace, machine.machine_type, for_service=True, for_booking=True))
    if not required:
        return []
    membership = MakerspaceMembership.objects.filter(
        makerspace_id=machine.makerspace_id, user=member, status="active").first()
    moment = now or timezone.now()
    return [row.name for row in required if active_grant(membership, row, moment) is None]


def _machine(machine, member, now):
    from apps.machines import booking_gate
    from apps.machines.lockout import require_not_locked_out
    from apps.machines.models import MachineServiceRequest, MachineSession
    if not machine.is_active or machine.status in DOWN:
        raise SessionRefused("machine_unavailable", "This machine is down or under maintenance.")
    require_not_locked_out(machine)
    from apps.machines.supervised import open_session_for
    if open_session_for(machine) is not None:
        raise SessionRefused("machine_in_use", "A supervised workshop session is using this machine.")
    booking_gate.check(machine, member, purpose="session", at=now)
    live = MachineSession.objects.filter(machine_id=machine.pk, ended_at__isnull=True).first()
    if live is not None and live.member_id == getattr(member, "pk", None):
        raise SessionRefused("session_already_live", "You already have a live session on this machine.",
                             session_id=live.pk)
    running_job = MachineServiceRequest.objects.filter(
        assigned_machine_id=machine.pk, status=MachineServiceRequest.Status.IN_PROGRESS).exists()
    if live is not None or running_job:
        raise SessionRefused("machine_in_use", "Someone is using this machine right now.")


def require_can_start(machine, member, *, now=None):
    now = now or timezone.now()
    _person(machine, member)
    missing = missing_certifications(machine, member, now) if _is_member(machine, member) else []
    if missing:
        raise SessionRefused("certification_required", "You need the certification for this machine first.",
                             status_code=403, certifications=missing)
    _machine(machine, member, now)


def refusal(machine, member, *, now=None):
    """The refusal `require_can_start` would raise, as `{code, detail, ...}`, or None."""
    try:
        require_can_start(machine, member, now=now)
    except APIException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {"detail": str(exc.detail)}
        return {key: value for key, value in detail.items()} | {"code": str(detail.get("code") or exc.default_code)}
    return None
