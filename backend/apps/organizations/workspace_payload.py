"""Decision 295: the organization page serves its workspace's public content.

When the organization's home space is an organization workspace (``Makerspace.kind``),
``/o/<slug>`` carries that space's upcoming listed events, public rooms and plans, so the
organization needs no separate /m/ page. Each part appears only while its module and
public surface are on; a makerspace-kind home space yields ``null`` (unchanged payload).
"""
from apps.makerspaces.module_registry import module_available
from apps.makerspaces.platform import module_enabled
from apps.makerspaces.space_kind import is_organization
from apps.organizations.public_plans import home_space, home_space_plans

EVENT_LIMIT = 12


def _events(space):
    from apps.makerspaces.editions import public_surface_available
    from apps.separability.registry import runtime_active
    if not (runtime_active("events") and module_available("events")
            and public_surface_available("events") and module_enabled(space, "events")):
        return None
    from apps.events.website_visibility import listed_events
    rows = listed_events(space).order_by("starts_at", "id")[:EVENT_LIMIT]
    return [{
        "title": event.title, "starts_at": event.starts_at, "ends_at": event.ends_at,
        "timezone": space.timezone, "location": event.location,
        "public_token": str(event.public_token),
    } for event in rows]


def _rooms(space):
    from apps.makerspaces.editions import public_surface_available
    if not (module_available("bookings") and public_surface_available("bookings")
            and module_enabled(space, "bookings")):
        return None
    from apps.bookings.website_visibility import public_spaces
    return [{"name": room.name, "kind": room.kind, "description": room.description,
             "public_token": str(room.public_token)}
            for room in public_spaces(space).order_by("name", "id")]


def workspace_payload(organization):
    space = home_space(organization)
    if space is None or not is_organization(space):
        return None
    from apps.makerspaces.space_kind import kind_payload
    return {**kind_payload(space), "name": space.name, "events": _events(space),
            "rooms": _rooms(space), "plans": home_space_plans(organization)}
