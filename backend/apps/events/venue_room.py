"""The room an event's linked reservation holds (decision 221(g)), for the public venue block.

Read-only. The event's retained `EventBookingDecision` names the ORIGINAL booking; the current
reservation is the tail of its `Booking.replaces` chain. Only a live (pending/confirmed) tail
counts, so a cancelled reservation never names a venue and the caller falls back to matching
the event's location text.
"""

from .booking_decision_replacement import MAX_CHAIN
from .models_booking_decision import EventBookingDecision

LIVE = ("pending", "confirmed")


def linked_room_id(event):
    """The `BookableSpace` id of the event's current live linked reservation, else None."""
    from apps.bookings.models import Booking
    decision = EventBookingDecision.objects.filter(event=event, booking__isnull=False).first()
    if decision is None:
        return None
    current = decision.booking
    for _step in range(MAX_CHAIN):
        nxt = Booking.objects.filter(replaces_id=current.pk).first()
        if nxt is None:
            break
        current = nxt
    return current.space_id if current.status in LIVE else None
