"""Presentation entries for Phase 2 bookings audit actions (gallery, departures, issues).

The existing dynamic booking namespace withholds all metadata, including IDs,
remarks, captions and object keys."""

from .presentation_catalog_types import P

ENTRIES = (
    P("booking.space_photo_added", "Space photo added"),
    P("booking.space_photo_updated", "Space photo caption updated"),
    P("booking.space_photo_removed", "Space photo removed"),
    P("booking.space_photos_reordered", "Space photos reordered"),
    P("booking.departure_recorded", "Booking departure recorded"),
    P("booking.issue_resolved", "Booking issue resolved"),
)
