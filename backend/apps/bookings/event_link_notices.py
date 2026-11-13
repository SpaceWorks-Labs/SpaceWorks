"""Bookings' only seam into event-link notices (decision 216).

After a booking is moved, cancelled, rejected or restored, the organizers of an event it
holds the room for are told (`events.linked_booking_notices`). Nothing happens -- and nothing about events is
imported -- while the events app is tombstoned or the space's `events` module is off, so
Bookings keeps working without Events. Call inside the booking's transaction; never raises.
"""

import logging

logger = logging.getLogger(__name__)


def booking_changed(booking, change):
    from apps.makerspaces.platform import module_enabled
    from apps.separability.tombstones import app_is_tombstoned
    try:
        if app_is_tombstoned("events") or not module_enabled(booking.space.makerspace, "events"):
            return None
        from apps.events.linked_booking_notices import notify_organizers
        return notify_organizers(booking, change)
    except Exception:  # a notice never blocks the booking decision
        logger.warning("booking_event_link_notice_failed", extra={"booking_id": booking.pk, "change": change})
        return None


def room_out_of_service(booking, outage):
    """A new room outage lists this booking: tell the organizers of an event it holds (if any)."""
    from apps.makerspaces.platform import module_enabled
    from apps.separability.tombstones import app_is_tombstoned
    try:
        if app_is_tombstoned("events") or not module_enabled(booking.space.makerspace, "events"):
            return None
        from apps.events.linked_outage_notices import notify_organizers
        return notify_organizers(booking, outage)
    except Exception:  # a notice never blocks taking the room out of service
        logger.warning("booking_event_outage_notice_failed", extra={"booking_id": booking.pk})
        return None
