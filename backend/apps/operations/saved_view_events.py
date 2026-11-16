"""Saved views that belong to ONE event's guest list (parity E-B5, B25; switch `events.event_saved_views`).

The event id lives in the view's `state` under `event` (state is the one place a view's filters are kept, and
a tenant import already resets it, so no foreign key has to be remapped). A view without it keeps its old
space-wide meaning; a view with it appears only for that event. The creator must hold the event's
`manage_registrations` permission, the event must belong to the space (anything else is a 404), and each person
may keep a limited number per event list (limit key `saved_views`, default none).
"""
from django.shortcuts import get_object_or_404

from apps.makerspaces.guards import require_feature

FEATURE = "events.event_saved_views"
KEY = "event"


def event_id_of(state):
    value = (state or {}).get(KEY)
    return int(value) if value not in (None, "") and str(value).isdigit() else None


def authorize(actor, space, entity, state):
    """Validate the event scope of a view being created or changed. Returns the event id or None."""
    if KEY not in (state or {}):
        return None
    from apps.events import event_authority
    from apps.events.models import Event
    from rest_framework.exceptions import ValidationError
    from django.utils.translation import gettext
    event_id = event_id_of(state)
    if event_id is None or not entity.startswith("event_"):
        raise ValidationError({"state": gettext("Only an event list can be saved for one event.")})
    require_feature(space, FEATURE)
    get_object_or_404(Event.objects.filter(makerspace=space), pk=event_id)
    event_authority.get_event(actor, event_id, "manage_registrations")
    return event_id


def check_quota(space, owner, entity, event_id, *, exclude_pk=None):
    from apps.managed_hosting.extra_quotas import check_scoped_quota  # `saved_views`: per person and list
    from .models_saved_views import SavedView
    rows = SavedView.objects.filter(makerspace=space, owner=owner, entity=entity, state__event=str(event_id))
    check_scoped_quota(space, "saved_views", rows.exclude(pk=exclude_pk).count() if exclude_pk else rows.count())


def narrow(rows, event_param):
    """Event-scoped views show only for their event; space-wide lists never include them."""
    if event_param:
        return rows.filter(state__event=str(event_param))
    return rows.exclude(state__has_key=KEY)
