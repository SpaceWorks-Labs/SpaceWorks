"""Audit presentation for lane L1: the public event surface (#21, #71, #73, #77).

Every `event.*` action sits under the dynamic event namespace (`events/services_core.py`
wraps runtime event actions), which withholds metadata at read time, so these entries
name the action only. The join link itself is never in an audit row in any case (only
whether it changed). The closed-for-now banner's leaves are public page facts.
"""

from django.utils.translation import gettext_noop
from .presentation_catalog_types import P

ENTRIES = (
    P("event.short_link.created", gettext_noop("Event short link created")),
    P("event.short_link.regenerated", gettext_noop("Event short link regenerated")),
    P("event.publishing_changed", gettext_noop("Event publishing changed")),
    P("event.delivery_mode_changed", gettext_noop("Event delivery mode changed")),
    P("event.embed_policy_updated", gettext_noop("Event embed allow-list updated")),
    P("makerspace.closed_notice_updated", gettext_noop("Closed-for-now banner updated"),
      ("notice_set", "reopens_on", "changed_fields")),
)
