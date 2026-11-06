"""Presentation entries for Phase 2 bookings audit actions (gallery, departures, issues).

The existing dynamic booking namespace withholds all metadata, including IDs,
remarks, captions and object keys."""

from django.utils.translation import gettext_noop
from .presentation_catalog_types import P

ENTRIES = (
    P("booking.space_photo_added", gettext_noop("Space photo added")),
    P("booking.space_photo_updated", gettext_noop("Space photo caption updated")),
    P("booking.space_photo_removed", gettext_noop("Space photo removed")),
    P("booking.space_photos_reordered", gettext_noop("Space photos reordered")),
    P("booking.departure_recorded", gettext_noop("Booking departure recorded")),
    P("booking.issue_resolved", gettext_noop("Booking issue resolved")),
)
