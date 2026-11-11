"""Independent event, booking and machine authority for workshop machine links (P2-1).

Three checks, none implied by another:

* the event -- `authorized_event` (events AND bookings modules, tenant-wide `manage_events`
  AND `manage_bookings`, event VIEW), plus the `machines` module;
* the booking -- `authorized_booking` (`manage_reservations` on its bookable resource);
* the machine -- `machines.access.can_manage_machine`, which narrows a Machine Manager to the
  machine types linked to their membership (per-type reach, fails closed) and admits a
  per-machine operator holding MANAGE. A booking manager without machine authority, or a
  Machine Manager scoped to another type, sees nothing (404).
"""
from rest_framework.exceptions import NotFound

from apps.makerspaces.guards import require_module
from .booking_decision_access import authorized_booking, authorized_event


def authorized_workshop_event(actor, makerspace, event_id):
    event = authorized_event(actor, makerspace, event_id)
    require_module(makerspace, "machines")
    return event


def machine_of(space):
    """The machine a bookable resource books, or None when it is not one machine's time."""
    if space.machine_id is None:
        return None
    from apps.machines.models import Machine
    return Machine.objects.select_related("makerspace", "machine_type").filter(
        pk=space.machine_id, makerspace_id=space.makerspace_id).first()


def can_manage_machine_space(actor, space):
    from apps.machines.access import can_manage_machine
    machine = machine_of(space)
    return machine is not None and can_manage_machine(actor, machine)


def authorized_machine_booking(actor, makerspace, booking_id):
    """`authorized_booking`, then authority over the exact machine the booking reserves."""
    booking = authorized_booking(actor, makerspace, booking_id)
    if not can_manage_machine_space(actor, booking.space):
        raise NotFound()
    return booking


def organizer_users(event):
    """The certification set (decision 226b): the creator plus every co-organizer holding manage_event.

    Co-organizers are the active members of the event's organizer organizations whose membership
    carries `manage_events` (the same authority `organizer_authority.can_manage_event` honours).
    """
    from apps.accounts import rbac
    from apps.accounts.models import User
    from apps.organizations.models import OrganizationMembership
    ids = {event.created_by_id} if event.created_by_id else set()
    memberships = OrganizationMembership.objects.filter(
        status=OrganizationMembership.Status.ACTIVE, organization__is_active=True,
        organization__organized_events__event=event,
    ).select_related("organization")
    ids.update(m.user_id for m in memberships
               if rbac.Action.MANAGE_EVENTS in rbac.actions_for_organization_membership(m))
    ids.update(_staff_grant_organizer_ids(event))
    return list(User.objects.filter(pk__in=ids).order_by("pk"))


def _staff_grant_organizer_ids(event):
    """Individual co-organizers: people with a live, unrestricted staff grant (or contribution role) that
    carries the event-management permission `edit_details` for this event (or its series). The grant
    vocabulary has no literal `manage_event`; `edit_details` is the permission that defines a co-organizer."""
    from django.db.models import Q
    from .contributions.authority import grant_ids
    from .models_staff_grants import EventStaffGrant
    rows = EventStaffGrant.objects.filter(revoked_at__isnull=True, makerspace_id=event.makerspace_id).filter(
        Q(event=event) | Q(series_id=event.series_id, series__isnull=False))
    live = grant_ids(permission="edit_details", scope_grants=rows)
    return set(rows.filter(pk__in=live).values_list("user_id", flat=True))


def require_organizer_certification(event, space, actor, override_reason=""):
    """Every organizer (creator and manage_event co-organizers) must hold the booking certification.

    Decisions 221b and 226b: checked alongside the booker's (`_require_certification`) with the
    same gate, override rules and audit. A non-member organizer cannot hold a certification and is
    REFUSED with `certification_required` (staff override with a reason), never skipped. A space
    whose machine type needs none is a no-op, exactly as for the booker.
    """
    if not space.machine_type_id:
        return
    from apps.bookings.services_bookings import _require_certification
    for organizer in organizer_users(event):
        _require_certification(space, organizer, actor, override_reason)
