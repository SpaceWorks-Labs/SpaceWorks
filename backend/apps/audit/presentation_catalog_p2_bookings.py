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
    P("booking.replacement_created", gettext_noop("Replacement booking created")),
    P("booking.included_hours_consumed", gettext_noop("Plan included hours used")),
    P("booking.included_hours_restored", gettext_noop("Plan included hours restored")),
    # B13: the organization hours bank (ids and minute counts only; the staff reason stays on the ledger row).
    P("booking.org_hours_consumed", gettext_noop("Organization hours used"), ("minutes",)),
    P("booking.org_hours_released", gettext_noop("Organization hours restored"), ("minutes",)),
    P("organization.hours_allowance_updated", gettext_noop("Organization hours allowance changed"),
      ("allowance_minutes", "period", "previous_allowance_minutes", "previous_period")),
    P("organization.hours_adjusted", gettext_noop("Organization hours granted or adjusted"), ("entry", "minutes")),
)
