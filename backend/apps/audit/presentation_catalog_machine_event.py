"""Presentation entries: machine use logged with an event (decision 342).

Ids, source codes and amounts only: never a person's name or a free-text note."""

from django.utils.translation import gettext_noop
from .presentation_catalog_types import P

_LINK = ("link_id", "session_id", "service_request_id", "event_id", "before_event_id", "after_event_id")

ENTRIES = (
    P("machine_event.linked", gettext_noop("Machine use linked to an event")),  # metadata is denied: the emitter builds meta at runtime
    P("machine_event.changed", gettext_noop("Machine use event changed"), _LINK),
    P("machine_event.cleared", gettext_noop("Machine use event cleared"), _LINK),
    P("machine_event.cost_approved", gettext_noop("Machine cost approved for the event")),
    P("machine_event.cost_withdrawn", gettext_noop("Machine cost approval withdrawn")),
)
