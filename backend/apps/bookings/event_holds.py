"""Bookings' seam into tentative event holds (decision 223 (m)).

A PENDING booking that holds a room for an event (the event's linked booking or a replacement
descending from it) holds its slot as tentative: admission and the availability views treat it
as busy so nobody else can take the slot while the venue awaits approval. Empty -- nothing is
held -- while the events app is tombstoned or the space's `events` module is off, so Bookings
keeps working without Events.
"""

from datetime import timedelta


def tentative_booking_ids(space, starts_at, ends_at):
    """Ids of pending, event-linked bookings of `space` whose occupied window meets the range."""
    from apps.makerspaces.platform import module_enabled
    from apps.separability.tombstones import app_is_tombstoned
    if app_is_tombstoned("events") or not module_enabled(space.makerspace, "events"):
        return []
    from apps.events.venue_holds import pending_linked_ids
    pad_before = timedelta(minutes=space.buffer_before_minutes + space.buffer_after_minutes)
    return pending_linked_ids(space, starts_at - pad_before, ends_at + pad_before)
