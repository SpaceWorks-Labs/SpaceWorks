"""Audit presentation for lane L1: the public event surface (#21, #71, #73, #77).

Every leaf is safe for the space's managers: short codes are public identifiers, the
publishing fields are the event's own visibility settings, and the embed allow-list names
partner origins. The join link itself is never in an audit row (only whether it changed).
"""

from .presentation_catalog_types import P

_PUBLISHING = ("is_public", "listing", "page_state", "registration_audience")

ENTRIES = (
    P("event.short_link.created", "Event short link created", ("event_id", "code")),
    P("event.short_link.regenerated", "Event short link regenerated", ("event_id", "code", "retired_code")),
    P("event.publishing_changed", "Event publishing changed", (
        "event_id", "changed_fields",
        *(f"before.{key}" for key in _PUBLISHING), *(f"after.{key}" for key in _PUBLISHING),
    )),
    P("event.delivery_mode_changed", "Event delivery mode changed",
      ("event_id", "old_mode", "new_mode", "join_url_changed", "join_url_set")),
    P("event.embed_policy_updated", "Event embed allow-list updated",
      ("enabled", "origin_count", "origins_added", "origins_removed", "via", "grant_id")),
    P("makerspace.closed_notice_updated", "Closed-for-now banner updated",
      ("notice_set", "reopens_on", "changed_fields")),
)
