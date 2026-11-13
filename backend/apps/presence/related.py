"""What else a person is doing around one live presence session, for staff.

Three optional neighbours of a check-in: the event registration it came from, a booking the person has
arrived for, and machine sessions they ran meanwhile. Each lives in an optional module and carries its own
authority, so each is shown only when that module is on for the space AND the viewer holds that area's
authority (event view, booking view, machine management scope). A neighbour the viewer may not see is
returned as nothing, never as a refusal, so the block cannot be used to probe whether it exists.
"""
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import APIException

from apps.accounts import rbac
from apps.makerspaces.platform import module_enabled


def _event(actor, space, session):
    registration = session.event_registration
    if registration is None or not module_enabled(space, "events"):
        return None
    from apps.events import event_authority
    from apps.events.event_permissions import VIEW
    event = registration.event
    if event.makerspace_id != space.pk or not event_authority.can(actor, event, VIEW):
        return None
    return {"event_id": event.pk, "title": event.title, "starts_at": event.starts_at,
            "ends_at": event.ends_at, "registration_status": registration.status}


def _booking(actor, space, session, window_end):
    if not module_enabled(space, "bookings"):
        return None
    from apps.bookings import booking_authority
    from apps.bookings.booking_permissions import VIEW
    from apps.bookings.models import Booking
    rows = Booking.objects.select_related("space").filter(
        space__makerspace=space, member_id=session.account_id, status__in=("confirmed", "completed"),
        arrived_at__isnull=False, arrived_at__lte=window_end,
    ).filter(Q(departed_at__isnull=True) | Q(departed_at__gte=session.started_at)).order_by("-arrived_at", "-pk")
    for booking in rows[:10]:
        if booking_authority.can(actor, booking.space, VIEW):
            return {"booking_id": booking.pk, "space_name": booking.space.name, "starts_at": booking.starts_at,
                    "ends_at": booking.ends_at, "arrived_at": booking.arrived_at, "status": booking.status}
    return None


def _machines(actor, space, session, window_end):
    if not module_enabled(space, "machines") or not rbac.can(actor, rbac.Action.MANAGE_MACHINES, space.pk):
        return []
    from apps.machines import access, sessions_state
    from apps.machines.models import Machine, MachineSession
    try:
        sessions_state.require_sessions(space)
    except APIException:
        return []
    machines = access.scope_machines_for_actor(actor, Machine.objects.filter(makerspace=space))
    rows = MachineSession.objects.select_related("machine").filter(
        makerspace=space, member_id=session.account_id, machine__in=machines, started_at__lte=window_end,
    ).filter(Q(ended_at__isnull=True) | Q(ended_at__gte=session.started_at)).order_by("-started_at", "-pk")[:20]
    return [{"session_id": row.pk, "machine_name": row.machine.name, "started_at": row.started_at,
             "ended_at": row.ended_at, "source": row.source} for row in rows]


def related_for(actor, space, session):
    window_end = session.ended_at or timezone.now()
    return {"event": _event(actor, space, session), "booking": _booking(actor, space, session, window_end),
            "machine_sessions": _machines(actor, space, session, window_end)}
