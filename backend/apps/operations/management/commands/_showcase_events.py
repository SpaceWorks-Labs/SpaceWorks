"""Showcase events for the public event surface (release 2 L1, #134 walkthrough).

Three published events, all through the real services: a listed hybrid evening with a
join link and a short link, an unlisted workshop reachable only by its link, and an
in-person repair cafe for the venue map link on the ticket.
"""

from datetime import timedelta

from django.utils import timezone

from apps.events import services, short_links
from apps.events.online_delivery import set_online

JOIN_LINK = "https://meet.example.org/tinkerspace-open-evening"


def _event(space, manager, title, *, days, listing="listed", location="Main workshop"):
    starts = (timezone.now() + timedelta(days=days)).replace(hour=18, minute=0, second=0, microsecond=0)
    event = services.create_event(
        makerspace=space, actor=manager, title=title, description=f"{title} at {space.name}.",
        starts_at=starts, ends_at=starts + timedelta(hours=2), location=location, capacity=30,
        is_public=True, listing=listing, registration_audience="accounts",
    )
    return services.publish(event, actor=manager)


def seed_events(space, manager):
    evening = _event(space, manager, "Open evening: show and tell", days=5)
    evening = set_online(evening, actor=manager, delivery_mode="hybrid", join_url_value=JOIN_LINK)
    short_links.create(evening, actor=manager)
    _event(space, manager, "Members' soldering clinic", days=9, listing="unlisted")
    _event(space, manager, "Repair cafe", days=12, location="Front room")
    return evening
