"""Read-only state of the room reservation an event holds (decision 223 (g), (m)).

The event's retained `EventBookingDecision` names the ORIGINAL booking; the current
reservation is the tail of its `Booking.replaces` chain. Nothing here writes. It feeds the
publish check (`venue_publish_check`), the capacity warning and the cancel/move offers
(`venue_offers`).

`state` is one of:

* `none`      -- no linked booking, or Bookings is off (the event holds no room; nothing to check);
* `confirmed` -- the current reservation is confirmed (or already completed / a no-show);
* `pending`   -- it awaits approval (holds its slot tentatively, decision 223 (m));
* `blocked`   -- it was rejected or cancelled (`reason`), the booking row is gone (`missing`) or
                 the room is no longer bookable (`unavailable`).
"""

from apps.makerspaces.platform import module_enabled

from .booking_decision_replacement import MAX_CHAIN
from .models_booking_decision import EventBookingDecision

CONFIRMED_LIKE = ("confirmed", "completed", "no_show")


def bookings_apply(event):
    from apps.separability.tombstones import app_is_tombstoned
    return (not app_is_tombstoned("bookings") and module_enabled(event.makerspace, "bookings"))


def current_booking(event):
    """`(decision, booking_or_None)`: the event's current reservation, no authorization.

    `decision` is None when the event was never linked. The booking is None when the link
    survives but the booking row was purged (`booking_id` is SET_NULL).
    """
    from apps.bookings.models import Booking
    decision = EventBookingDecision.objects.filter(event=event).first()
    if decision is None:
        return None, None
    if decision.booking_id is None:
        return decision, None
    current = Booking.objects.select_related("space").filter(pk=decision.booking_id).first()
    for _step in range(MAX_CHAIN):
        if current is None:
            return decision, None
        nxt = Booking.objects.select_related("space").filter(replaces_id=current.pk).first()
        if nxt is None:
            break
        current = nxt
    return decision, current


def coverage(event, booking):
    covered = booking.starts_at <= event.starts_at and event.ends_at <= booking.ends_at
    return "covers" if covered else "not_covered"


def venue_state(event):
    """The venue state dict every venue check reads; cheap, read-only, never raises."""
    if not bookings_apply(event):
        return {"state": "none", "reason": "", "booking_id": None}
    decision, booking = current_booking(event)
    if decision is None:
        return {"state": "none", "reason": "", "booking_id": None}
    if booking is None:
        return {"state": "blocked", "reason": "missing", "booking_id": None}
    base = {"booking_id": booking.pk, "booking_status": booking.status, "space_id": booking.space_id,
            "space_name": booking.space.name, "coverage": coverage(event, booking),
            "is_house": getattr(booking, "is_house", False)}
    if booking.status in ("rejected", "cancelled"):
        return {**base, "state": "blocked", "reason": booking.status}
    if not booking.space.is_active:
        return {**base, "state": "blocked", "reason": "unavailable"}
    if booking.status == "pending":
        return {**base, "state": "pending", "reason": ""}
    return {**base, "state": "confirmed", "reason": ""}
