import math
from datetime import timedelta

from apps.events.models import EventRegistration


CONFIRMED_STATUSES = (
    EventRegistration.Status.REGISTERED,
    EventRegistration.Status.ATTENDED,
)


def confirmed_occupancy(event):
    confirmed = getattr(event, 'confirmed_count', None)
    if confirmed is None:
        confirmed = event.registrations.filter(
            status__in=CONFIRMED_STATUSES
        ).count()
    return confirmed


def spots_left(event):
    if event.capacity == 0:
        return None
    return max(event.capacity - confirmed_occupancy(event) - unused_contributor_reservations(event), 0)


def unused_contributor_reservations(event):
    """Unused configured reserved seats are unavailable to participant admission."""
    return sum(max(ticket.capacity - event.registrations.filter(ticket_type=ticket,
        status__in=CONFIRMED_STATUSES).count(), 0) for ticket in event.ticket_types.filter(
            purpose="contributor", contributor_capacity_policy="reserved_contributor_capacity", is_active=True))


def availability_label(event, *, reservations=True):
    """`reservations=False` is the discovery card's coarse label: one annotated page
    query and no ticket reads. Admission and event detail keep the exact count."""
    if event.capacity == 0:
        return 'Available'
    left = spots_left(event) if reservations else max(event.capacity - confirmed_occupancy(event), 0)
    if left <= 0:
        return 'Full'
    if left <= math.ceil(event.capacity * 0.2):
        return 'Limited'
    return 'Available'


def effective_registration_cutoff(event):
    if event.registration_cutoff_at is not None:
        return event.registration_cutoff_at
    if event.registration_cutoff_lead_minutes is not None:
        return event.starts_at - timedelta(
            minutes=event.registration_cutoff_lead_minutes
        )
    return None


def registration_is_open(event, now):
    if event.status != event.Status.PUBLISHED or now >= event.ends_at:
        return False
    cutoff = effective_registration_cutoff(event)
    return cutoff is None or now < cutoff


def ticket_spots_left(event, ticket):
    if ticket is None or ticket.capacity == 0:
        return None
    occupied = getattr(ticket, "confirmed_count", None)
    if occupied is None:
        occupied = event.registrations.filter(ticket_type=ticket, status__in=CONFIRMED_STATUSES).count()
    return max(ticket.capacity - occupied, 0)


def registration_spots_left(event, ticket=None):
    event_left = (max(event.capacity - confirmed_occupancy(event), 0) if event.capacity else None) if (
        ticket and ticket.purpose == "contributor") else spots_left(event)
    limits = [value for value in (event_left, ticket_spots_left(event, ticket)) if value is not None]
    return min(limits) if limits else None


def fresh_registration_status(event, ticket=None, *, approval_granted=False):
    """Choose admission state, retaining a proven approval during cancellation undo."""
    if event.registration_requires_approval and not approval_granted:
        return EventRegistration.Status.PENDING_APPROVAL
    available = registration_spots_left(event, ticket)
    if available is None or available > 0:
        return EventRegistration.Status.REGISTERED
    return EventRegistration.Status.WAITLISTED


def require_contributor_room_locked(*, event_id, ticket_type_id, assignment_id, locks):
    from .programme_locks import assert_lock_context
    from .models import Event, EventTicketType
    from .contributions.models_roles import EventRoleAssignment
    from .hackathons.admission_errors import fail
    assert_lock_context(locks)
    if locks.event_id != event_id:
        raise RuntimeError("Use the declared event context.")
    event = Event.objects.get(pk=event_id)
    ticket = EventTicketType.objects.get(pk=ticket_type_id, event_id=event_id,
        makerspace_id=event.makerspace_id, purpose="contributor", is_active=True)
    if (ticket.contributor_capacity_policy != "reserved_contributor_capacity" or ticket.capacity == 0
            or not EventRoleAssignment.objects.filter(pk=assignment_id, event_id=event_id,
                state="approved", imported_inert=False, member_id__in=locks.account_ids).exists()):
        fail("invalid_capacity_policy", "Choose a configured reserved contributor ticket.", status=400)
    available = registration_spots_left(event, ticket)
    if available is not None and available <= 0:
        fail("capacity_full", "No reserved contributor places are available.")
