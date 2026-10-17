"""Independently reviewed website retention snapshot. No User edges or credentials.

Curated publication text is public editorial data, like event title/description,
not a private contact/answer store; no scoped-PII field or encryption write fence.
"""

FIELD_NAMES = {
    'bookings.BookingResourcePage': frozenset('id space released revision updated_at'.split()),
    'bookings.BookingResourcePageAsset': frozenset('id page object_key size_bytes alt_text created_at'.split()),
    'bookings.BookingResourcePageSection': frozenset('id page kind slug title body url asset visibility position'.split()),
    'events.EventPage': frozenset('id makerspace event series released revision updated_at tagline accent_color section_order section_enabled venue'.split()),
    'events.EventPageAsset': frozenset('id page object_key size_bytes alt_text created_at'.split()),
    'events.EventPageSection': frozenset('id page kind slug title body url asset visibility position headline organization website_url linkedin_url x_url sponsor_tier icon'.split()),
    'events.EventSession': frozenset('id page slug title body starts_at ends_at track room delay_minutes visibility'.split()),
    'events.EventSessionSpeaker': frozenset('id session speaker'.split()),
}
EXPORTED_FIELDS = {label: " ".join(sorted(names)) for label, names in FIELD_NAMES.items()}
FIELD_NAMES["events.EventPage"] |= {"draft_revision", "published_revision", "editorial_document"}
FIELD_NAMES["events.EventSession"] |= {"identity"}
EXPORTED_FIELDS = {label: " ".join(sorted(names)) for label, names in FIELD_NAMES.items()}
