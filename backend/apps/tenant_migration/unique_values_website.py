"""Typed website references remap; private asset ownership uses target-local page IDs."""

from .unique_values_policy import REMAP, _policy


WEBSITE_UNIQUE_RULES = {
    # Keys are remapped before row insertion, not immutable source identities.
    # The object journal allocates collisions and keeps rows and bytes in sync.
    ("bookings.BookingResourcePageAsset", "field:object_key"): _policy(REMAP, "Verified object journal allocates collision-safe private keys."),
    ("events.EventPage", "field:event"): _policy(REMAP, "Typed owner follows the imported event."),
    ("events.EventPage", "field:series"): _policy(REMAP, "Typed owner follows the imported series."),
    ("events.EventPageAsset", "field:object_key"): _policy(REMAP, "The verified import journal allocates collision-safe keys before row insertion."),
}
