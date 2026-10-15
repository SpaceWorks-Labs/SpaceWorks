"""Typed website references remap; private asset ownership uses target-local page IDs."""

from .unique_values_policy import PRESERVE, REMAP, _policy


def asset_key(row, target, source_value):
    raise RuntimeError("Website asset collision escaped the verified import object journal.")


asset_key.refuses_collision = True


WEBSITE_UNIQUE_RULES = {
    ("events.EventPage", "field:event"): _policy(REMAP, "Typed owner follows the imported event."),
    ("events.EventPage", "field:series"): _policy(REMAP, "Typed owner follows the imported series."),
    ("events.EventPageAsset", "field:object_key"): _policy(PRESERVE, "The verified import journal allocates collision-safe keys before row insertion.", field="object_key", generator=asset_key),
}
