"""Pending bookings that hold a room for an event (decision 223 (m)); read-only.

`bookings.event_holds` is the only caller. A booking counts when it is the event's retained
decision booking or a replacement descending from it (`Booking.replaces`), as in
`booking_calendar_labels`, and the event is still live (draft or published).
"""

from .booking_calendar_labels import _roots
from .models import Event
from .models_booking_decision import EventBookingDecision


def pending_linked_ids(space, starts_at, ends_at):
    from apps.bookings.models import Booking
    pending = list(Booking.objects.filter(
        space=space, status=Booking.Status.PENDING, starts_at__lt=ends_at, ends_at__gt=starts_at,
    ).values_list("pk", flat=True))
    if not pending:
        return []
    roots = _roots(pending)
    linked = set(EventBookingDecision.objects.filter(
        booking_id__in=set(roots.values()), event__status__in=(Event.Status.DRAFT, Event.Status.PUBLISHED),
    ).values_list("booking_id", flat=True))
    return [pk for pk in pending if roots[pk] in linked]
