"""A member booker cancelling a room that hosts an event must be told, and confirm (decision 223 (m)).

The label comes from `event_labels` (Bookings' only seam into events), so it is empty while the
events app is tombstoned or the space's `events` module is off. The event title is shown only
when the booker may see that event; otherwise the label is the generic `reserved`. Staff
cancellations are not guarded here: staff see the event on the booking and the event's
organizers are always notified (`event_link_notices`).
"""

from rest_framework.exceptions import APIException

from apps.audit import services as audit

CODE = "booking_hosts_event"


class BookingHostsEvent(APIException):
    status_code = 409
    default_code = CODE

    def __init__(self, label):
        super().__init__({"detail": "This room is held for an event. Cancelling it removes the event's "
                                    "room. Confirm to cancel anyway.", "code": CODE, "event": label})


def hosted_event_label(actor, booking):
    """`{kind: 'event'|'reserved', ...}` when this booking (or an ancestor) holds a room for an event."""
    from .event_labels import event_labels
    return event_labels(actor, booking.space.makerspace, [booking.pk]).get(booking.pk)


def require_confirmation(booking, actor, confirmed):
    """Raise `BookingHostsEvent` unless confirmed. Returns the label when the cancel was confirmed."""
    label = hosted_event_label(actor, booking)
    if label is None:
        return None
    if not confirmed:
        raise BookingHostsEvent(label)
    return label


def record_confirmed(booking, actor, label):
    if label is not None:
        audit.record(actor, "booking.cancelled_event_room_confirmed", makerspace=booking.space.makerspace,
                     target=booking, meta={"booking_id": booking.pk})
