"""Presentation entries for Phase 2 bookings audit actions (gallery, departures, issues).

Only reviewed non-personal leaf paths are permitted: never the remark text, captions or
object keys."""

from .presentation_catalog_types import P

ENTRIES = (
    P("booking.space_photo_added", "Space photo added", ("photo_id", "position")),
    P("booking.space_photo_updated", "Space photo caption updated", ("photo_id",)),
    P("booking.space_photo_removed", "Space photo removed", ("photo_id",)),
    P("booking.space_photos_reordered", "Space photos reordered", ("count",)),
    P("booking.departure_recorded", "Booking departure recorded",
      ("booking_id", "outcome", "source", "has_remark", "issue_id")),
    P("booking.issue_resolved", "Booking issue resolved", ("issue_id", "booking_id", "outcome")),
)
