"""Authorized replacement of a rejected or cancelled linked reservation (decision 216).

The event's `EventBookingDecision` is immutable and keeps naming the ORIGINAL booking;
each replacement is a booking-owned `Booking.replaces` edge created through ordinary
booking admission (`bookings.services_replacement`). The event's current reservation
is the tail of that chain, and every earlier booking keeps its own status, frozen price,
debt and receipts. The venue stays booking-owned throughout, so no event venue fee can
be raised for the replacement (`venue_fees` refuses whenever a decision exists).

Event and room authority are verified independently: tenant-wide events AND bookings
roles plus event visibility (`authorized_event`), `manage_reservations` on the current
reservation's room, and `manage_reservations` on the replacement room.
"""

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import NotFound

from apps.audit.services import record
from .booking_decision_access import authorized_booking, authorized_event
from .booking_decision_service import DecisionConflict
from .models_booking_decision import EventBookingDecision

#: A chain longer than this is refused rather than walked without bound.
MAX_CHAIN = 50


def reservation_chain(actor, maker, decision, *, authorize=authorized_booking):
    """The original linked booking then each replacement, oldest first, each authorized."""
    from apps.bookings.models import Booking
    if decision.booking_id is None:
        return []
    chain = [authorize(actor, maker, decision.booking_id)]
    while True:
        nxt = Booking.objects.filter(replaces_id=chain[-1].pk).values_list("pk", flat=True).first()
        if nxt is None:
            return chain
        if len(chain) >= MAX_CHAIN:
            raise DecisionConflict("replacement_history_requires_review")
        chain.append(authorize(actor, maker, nxt))


def replaceable(event, booking):
    from apps.bookings.services_replacement import REPLACEABLE
    return (event.status in (event.Status.DRAFT, event.Status.PUBLISHED)
            and booking.status in REPLACEABLE)


@transaction.atomic
def replace_linked(actor, maker, event_id, *, expected_booking_id, space_id, member_id,
                   starts_at, ends_at, price_confirmation, note=""):
    from apps.bookings.booking_authority import get_space
    from apps.bookings.models import BookableSpace
    from apps.bookings.services_replacement import replace_booking
    from apps.bookings.views_admin_booking_create import _members
    from apps.presence.guard import require_active_member

    event = authorized_event(actor, maker, event_id)
    decision = EventBookingDecision.objects.filter(makerspace_id=maker.pk, event_id=event.pk).first()
    if decision is None or decision.booking_id is None:
        raise NotFound()
    current = reservation_chain(actor, maker, decision)[-1]
    if current.pk != expected_booking_id:
        raise DecisionConflict("stale_context")
    if not replaceable(event, current):
        raise DecisionConflict("replacement_not_allowed")
    space = get_space(actor, space_id, "manage_reservations")
    if (space.makerspace_id != maker.pk or not space.is_active
            or space.kind == BookableSpace.Kind.MACHINE or space.machine_id is not None):
        raise NotFound()
    membership = get_object_or_404(_members(actor, space), user_id=member_id)
    require_active_member(membership.user, maker)
    replacement = replace_booking(current, space=space, member=membership.user, starts_at=starts_at,
                                  ends_at=ends_at, actor=actor, price_confirmation=price_confirmation,
                                  note=note)
    # IDs live on the booking-owned audit row; the event row names only the operation.
    record(actor, "event.booking_decision_replaced", makerspace=maker, target=event,
           meta={"domain": "booking", "operation": "replaced"})
    return replacement
