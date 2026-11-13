"""Tag and organiser narrowing for public event discovery (parity E-B7, `events.discovery_filters`).

Everything here only ever narrows an already-public queryset (listed, live, servable). Organisers count only
when they are publicly visible organisations: active, approved and with their public profile on, so a private
organisation's name can neither be searched nor filtered on. A space with the switch off is left out of the
narrowed results rather than silently ignoring the filter. Organiser conditions use subqueries, never joins,
because the discovery queryset already aggregates registrations and a join would multiply those counts.
"""

from apps.makerspaces.platform import feature_enabled

from .organizer_models import EventOrganizer

FEATURE = "events.discovery_filters"
MIN_QUERY = 2


def _allowed_space_ids(spaces):
    return [space.pk for space in spaces if feature_enabled(space, FEATURE)]


def _public_organizers(spaces, **lookups):
    return EventOrganizer.objects.filter(
        organization__is_active=True, organization__public_profile_enabled=True,
        organization__review_status="approved", event__makerspace_id__in=_allowed_space_ids(spaces), **lookups,
    ).values("event_id")


def organizer_name_matches(spaces, text):
    """Subquery of event ids whose public organiser name contains the text, or None when too short."""
    if len(text) < MIN_QUERY:
        return None
    return _public_organizers(spaces, organization__name__icontains=text)


def restrict_by_tag_and_organization(rows, spaces, tag, organization):
    tag = (tag or "").strip()
    organization = (organization or "").strip()
    if not tag and not organization:
        return rows
    rows = rows.filter(makerspace_id__in=_allowed_space_ids(spaces))
    if tag:
        # Case-insensitive match on one whole tag, never a substring of another tag.
        rows = rows.extra(where=["EXISTS (SELECT 1 FROM jsonb_array_elements_text(events_event.tags) AS t(v) "
                                 "WHERE lower(t.v) = lower(%s))"], params=[tag])
    if organization:
        rows = rows.filter(pk__in=_public_organizers(spaces, organization__slug=organization))
    return rows


def discoverable_organizers(spaces):
    """`slug` and `name` of the public organisations that organise at least one event Discover lists right now.

    The events are exactly the Discover list (listed, published, not ended, servable, on a directory space), narrowed to
    spaces with the switch on, so the picker can never offer an organiser the organisation filter would refuse.
    """
    from apps.organizations.models import Organization

    from .website_visibility import discover_events
    events = discover_events(spaces).filter(makerspace_id__in=_allowed_space_ids(spaces)).order_by().values("pk")
    organizers = EventOrganizer.objects.filter(event_id__in=events).values("organization_id")
    return (Organization.objects.filter(pk__in=organizers, is_active=True, public_profile_enabled=True,
                                        review_status="approved").order_by("name", "pk").values("slug", "name"))
