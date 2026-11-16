"""Events attended and certifications of the global profile (decisions 303c, 304c).

Both aggregate across the person's spaces, under one rule: only spaces where the person is an
ACTIVE member of a servable, directory-listed space (`account_profile_spaces.listed_space_ids`),
and only events a stranger could see in the public catalogue -- never private, invite-only or
unlisted events, never an unpublished one. Re-read on every request; nothing is stored.
"""

from .account_profile_spaces import listed_memberships, listed_space_ids
from .platform import module_enabled

RECENT_LIMIT = 20


def event_is_public(event):
    """The same visibility a stranger gets from the events catalogue, plus a live host."""
    from .servability import is_servable

    return bool(
        event.is_public and event.listing == "listed" and event.page_state == "live"
        and event.status in ("published", "completed")
        and is_servable(event.makerspace) and module_enabled(event.makerspace, "events")
    )


def _event_space_ids(user):
    from .models import Makerspace

    ids = listed_space_ids(user)
    return [space.pk for space in Makerspace.objects.filter(pk__in=ids) if module_enabled(space, "events")]


def attended_registrations(user):
    from apps.events.models import EventRegistration

    return EventRegistration.objects.filter(
        member=user, status=EventRegistration.Status.ATTENDED,
        event__makerspace_id__in=_event_space_ids(user),
        event__is_public=True, event__listing="listed", event__page_state="live",
        event__status__in=("published", "completed"),
    )


def attended_events(user, only_space_id=None):
    """`{count, recent}`; `count` is distinct events, `recent` at most 20, newest first.

    `only_space_id` narrows to one host space: a claim session is scoped to a single tenant and must
    never see another space's events.
    """
    rows = attended_registrations(user)
    if only_space_id is not None:
        rows = rows.filter(event__makerspace_id=only_space_id)
    count = rows.values("event_id").distinct().count()
    recent = rows.select_related("event__makerspace").order_by("-event__starts_at", "-id")[:RECENT_LIMIT]
    return {"count": count, "recent": [
        {"id": row.event_id, "title": row.event.title, "starts_at": row.event.starts_at,
         "space_name": row.event.makerspace.name} for row in recent]}


def certifications(user, memberships=None):
    """Live certification names from every listed space (or the given ones), tagged with the space name."""
    from apps.machines.certifications import live_certification_names

    result = []
    for membership in listed_memberships(user) if memberships is None else memberships:
        for name in live_certification_names(membership):
            result.append({"name": name, "space_name": membership.makerspace.name})
    return result
