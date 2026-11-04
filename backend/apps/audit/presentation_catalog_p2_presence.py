from .presentation_catalog_types import P

ENTRIES = (
    P("presence.preference_updated", "Presence display preference changed"),
    P("presence.settings_updated", "Presence display settings changed"),
    P("presence.renewed", "Presence renewed"),
    P("presence.expired", "Presence expired"),
    P("presence.expiry_reminded", "Presence expiry reminder queued"),
    P("presence.expiry_reminder_skipped", "Stale presence reminder skipped"),
)
