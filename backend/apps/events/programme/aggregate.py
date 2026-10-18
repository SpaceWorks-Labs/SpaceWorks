"""The shared aggregate envelope for operation projections."""

from apps.events import event_authority
from apps.events.event_permissions import PERMISSIONS

from .commands import event_version


def aggregate(event, actor):
    return {"id": event.pk, "event_id": event.pk, "version": event_version(event),
            "state": event.status,
            "allowed_actions": [key for key in PERMISSIONS if event_authority.can(actor, event, key)]}
