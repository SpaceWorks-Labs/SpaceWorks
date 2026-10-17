"""Phase 2 event labels; the existing dynamic event namespace withholds metadata."""
from .presentation_catalog_types import P

ENTRIES = (
    P("event.speaker_assigned", "Event speaker assigned"),
    P("event.speaker_invited", "Event speaker invited"),
    P("event.speaker_claimed", "Event speaker invitation claimed"),
    P("event.speaker_removed", "Event speaker removed"),
    P("event.ticket_updated", "Event ticket type updated"),
    P("event.ticket_deleted", "Event ticket type deleted"),
    P("event.category_updated", "Event category updated"),
    P("event.category_deleted", "Event category deleted"),
)
