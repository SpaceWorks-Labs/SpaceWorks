"""Busy VEVENTs for personal booking feeds, only where unavailable time meets the reader's OWN booking.

A member's feed never describes a room they have not booked, nor anyone else's booking: it
adds an opaque block only where their own upcoming reservation overlaps time the room is out
(`Unavailable`) or the space is closed (`Space closed`). Public labels only (`busy_overlay`),
so no outage reason and no repair detail ever reaches a feed. DTSTAMP is derived from the
source row, never the clock.
"""

from django.utils import timezone
from django.utils.translation import gettext

LIMIT = 50
LIVE = ("pending", "confirmed")


def busy_components(bookings):
    """VEVENTs (TRANSP:OPAQUE) for the unavailable parts of the next `LIMIT` live bookings in `bookings`."""
    from icalendar import Event

    from .busy_overlay import CLOSED, feed_blocks

    now = timezone.now()
    rows = bookings.filter(status__in=LIVE, ends_at__gt=now).select_related(
        "space__makerspace").order_by("starts_at", "pk")[:LIMIT]
    components = []
    for booking in rows:
        for block in feed_blocks(booking.space, booking.starts_at, booking.ends_at):
            event = Event()
            event.add("uid", f"busy-{booking.public_token}-{block['kind']}-"
                             f"{int(block['starts_at'].timestamp())}@spaceworks")
            # Stable: the later of the source row's start and the booking's last change, never
            # "now", so a calendar client does not see every poll as an update.
            stamp = max(value for value in (block["since"], booking.calendar_updated_at) if value)
            event.add("dtstamp", stamp)
            event.add("last-modified", stamp)
            event.add("dtstart", block["starts_at"])
            event.add("dtend", block["ends_at"])
            event.add("summary", gettext("Space closed") if block["kind"] == CLOSED else gettext("Unavailable"))
            event.add("transp", "OPAQUE")
            event.add("status", "CONFIRMED")
            components.append(event)
    return components
