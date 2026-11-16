"""Publish check for an event's venue (decision 223 (g)).

* The linked booking is pending: publishing WARNS (the room is held tentatively, never confirmed).
* It was rejected, cancelled, is missing or its room is gone: publishing is BLOCKED unless the
  organizer explicitly chooses "publish without room", which is audited.
* A legacy venue fee is never charged for a room the event does not hold: the fee is skipped
  when the organizer publishes without a room, and is disclosed in the preview otherwise.

`publish_check` is read-only and backs the publish dialog (`GET .../publish-check`).
"""

from rest_framework.exceptions import APIException

from .audience_default import needs_fallback
from .venue_state import venue_state


class VenueBlocked(APIException):
    status_code = 409
    default_code = "venue_booking_blocked"

    def __init__(self, state):
        super().__init__({"detail": "The room booking for this event is not usable. Replace it or "
                                    "publish without a room.", "code": self.default_code,
                          "venue": state})


def room_capacity_warning(event, space_capacity):
    """Event capacity above the room's capacity warns; it never blocks (decision 223 (m))."""
    if event.capacity and space_capacity and event.capacity > space_capacity:
        return {"code": "event_capacity_above_room", "event_capacity": event.capacity,
                "room_capacity": space_capacity}
    return None


def _fee_disclosure(event):
    from .models import EventVenueFee
    fee = EventVenueFee.objects.filter(event=event, status=EventVenueFee.Status.CONFIGURED).first()
    if fee is None:
        return None
    return {"will_charge_on_publish": True, "mode": fee.mode}  # m22: the payer id stays off the read-only panel


def _room_capacity(venue):
    if not venue.get("space_id"):
        return 0
    from apps.bookings.models import BookableSpace
    return BookableSpace.objects.filter(pk=venue["space_id"]).values_list("capacity", flat=True).first() or 0


def publish_check(event):
    venue = venue_state(event)
    warnings = []
    if venue["state"] == "pending":
        warnings.append({"code": "venue_pending"})
    if venue["state"] in ("pending", "confirmed") and venue.get("coverage") == "not_covered":
        warnings.append({"code": "venue_not_covered"})
    capacity = room_capacity_warning(event, _room_capacity(venue)) if venue["state"] in ("pending", "confirmed") else None
    if capacity:
        warnings.append(capacity)
    if needs_fallback(event):
        warnings.append({"code": "audience_falls_back_to_accounts"})
    blocked = venue["state"] == "blocked"
    return {"venue": venue, "warnings": warnings, "requires_override": blocked,
            "can_publish": not blocked, "venue_fee": None if blocked else _fee_disclosure(event)}


def enforce_on_publish(event, *, publish_without_room):
    """Raise `VenueBlocked` for a blocked venue unless overridden. Returns the venue state."""
    venue = venue_state(event)
    if venue["state"] == "blocked" and not publish_without_room:
        raise VenueBlocked(venue)
    return venue
