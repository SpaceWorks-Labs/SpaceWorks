"""Phase 2 events lane: speaker identity and ticket/category edits. Metadata is enums/field names only."""
from .presentation_catalog_types import P

ENTRIES = (
    P("event.speaker_assigned", "Event speaker assigned", ("linked_via", "grants_check_in")),
    P("event.speaker_invited", "Event speaker invited", ("grants_check_in",)),
    P("event.speaker_claimed", "Event speaker invitation claimed", ("linked_via",)),
    P("event.speaker_removed", "Event speaker removed"),
    P("event.ticket_updated", "Event ticket type updated", ("fields",)),
    P("event.ticket_deleted", "Event ticket type deleted"),
    P("event.category_updated", "Event category updated", ("fields",)),
    P("event.category_deleted", "Event category deleted"),
)
