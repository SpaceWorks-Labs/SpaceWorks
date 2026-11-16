"""THE decision on whether a member may use a machine (decision 319).

Machine use is granted by the Space Manager (or a Machine Manager inside their machine scope).
Certifications, trainings and inductions no longer gate anything. Every caller asks this module and
nothing else: machine sessions (`sessions_rules`), job requests (`service_workflow_*`), machine
bookings (`bookings.services_bookings`), event machine links, guest machine modes and the adapter's
`access.authorize` (through `sessions_rules.refusal`).

* ``can_use(member, machine)`` -> ``(allowed, reason)``; reason is ``None`` or ``no_machine_access`` /
  ``machine_access_expired``.
* ``can_use_type(member, makerspace, machine_type)`` is the same question for callers that hold only a
  machine TYPE (a job request, a bookable space linked to a type).
* ``require_access`` / ``require_type_access`` raise ``MachineAccessRefused`` (403, code = reason).

A machine "open to all members" needs no grant. Supervision is a separate machine setting and is not
decided here. Fails closed: no member, or an unreadable grant, is a refusal.
"""
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext
from rest_framework.exceptions import PermissionDenied

NO_ACCESS = "no_machine_access"
EXPIRED = "machine_access_expired"
REASON_TEXT = {
    NO_ACCESS: "You have not been given access to this machine. Ask a space manager.",
    EXPIRED: "Your access to this machine has expired. Ask a space manager to renew it.",
}


class MachineAccessRefused(PermissionDenied):
    default_code = NO_ACCESS

    def __init__(self, reason):
        super().__init__({"detail": gettext(REASON_TEXT[reason]), "code": reason}, reason)
        self.code = reason


def _grants(member, makerspace_id):
    from .models import MachineAccessGrant
    return MachineAccessGrant.objects.filter(makerspace_id=makerspace_id, member=member, revoked_at__isnull=True)


def _verdict(grants, now):
    rows = list(grants)
    if any(row.expires_at is None or row.expires_at > now for row in rows):
        return True, None
    return False, (EXPIRED if rows else NO_ACCESS)


def can_use(member, machine, *, now=None, include_open=True):
    """``(allowed, reason)`` for `member` on `machine`. `include_open=False` ignores "open to all members"
    (a guest-pass holder is not a member, so an open machine does not admit them)."""
    if member is None or not getattr(member, "pk", None) or machine is None:
        return False, NO_ACCESS
    if include_open and machine.open_to_all_members:
        return True, None
    moment = now or timezone.now()
    scope = Q(machine_id=machine.pk) | Q(machine_type_id=machine.machine_type_id, machine__isnull=True)
    return _verdict(_grants(member, machine.makerspace_id).filter(scope), moment)


def can_use_type(member, makerspace, machine_type, *, now=None, include_open=True):
    """The same question for a machine TYPE: any open machine of the type, a type grant, or a grant on any
    machine of the type. A type with no active machine has nothing to gate, so it admits (the request cannot
    be served until a machine exists)."""
    from .models import Machine
    if member is None or not getattr(member, "pk", None) or makerspace is None or machine_type is None:
        return False, NO_ACCESS
    machines = Machine.objects.filter(makerspace=makerspace, machine_type=machine_type, is_active=True)
    if include_open and not machines.exists():
        return True, None
    if include_open and machines.filter(open_to_all_members=True).exists():
        return True, None
    scope = Q(machine_type_id=machine_type.pk, machine__isnull=True) | Q(machine__machine_type_id=machine_type.pk)
    return _verdict(_grants(member, makerspace.pk).filter(scope), now or timezone.now())


def require_access(member, machine, *, now=None):
    allowed, reason = can_use(member, machine, now=now)
    if not allowed:
        raise MachineAccessRefused(reason)


def require_type_access(member, makerspace, machine_type, *, now=None):
    allowed, reason = can_use_type(member, makerspace, machine_type, now=now)
    if not allowed:
        raise MachineAccessRefused(reason)


def live_grants_for(member, makerspace_id, now=None):
    """The member's live, unexpired grants (for "My machine access")."""
    moment = now or timezone.now()
    return _grants(member, makerspace_id).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=moment))
