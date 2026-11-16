"""Phase 2 events lane: object routes resolved to their makerspace for origin scoping."""

P2_EVENT_MODEL_LOOKUPS = {
    "admin-event-speakers": ("events.Event", "makerspace_id"),
    "admin-event-speaker-invite": ("events.Event", "makerspace_id"),
    "admin-event-speaker-candidates": ("events.Event", "makerspace_id"),
    "admin-event-speaker-remove": ("events.EventSpeaker", "makerspace_id"),
    "admin-event-ticket-detail": ("events.EventTicketType", "makerspace_id"),
}
