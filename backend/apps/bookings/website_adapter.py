"""Booking adapter for shared embeds, share HTML, directory and sitemap projections."""

from apps.makerspaces.resource_clone_extensions import register_clone_extension
from apps.makerspaces.website_directory import public_url
from apps.makerspaces.website_serving import PublicCard
from apps.makerspaces.website_visibility import WebsiteAdapter, register
from . import storage
from .serializers_website import BookingDiscoveryFilters
from .website_copy import copy_page
from .website_visibility import resolve, visible_page, discover_spaces


def card(space):
    page = getattr(space, "website_page", None)
    revision = f"{page.pk}:{page.revision}:{page.released}" if page else "core"
    return PublicCard(
        title=space.name, description=space.description[:300],
        url=public_url(space.makerspace, "bookings", space.public_token),
        image_url=storage.public_url(space.image_key) or None,
        date="", location=space.location,
        availability="Choose a time to check availability", audience_label="",
        makerspace_name=space.makerspace.name,
        revision=f"{space.makerspace_id}:{space.pk}:{space.updated_at.isoformat()}:{revision}:{space.makerspace.updated_at.isoformat()}",
    )


def register_website():
    register(WebsiteAdapter(kind="bookings", module="bookings", resolve=resolve,
                           discover=discover_spaces, card=card, page=visible_page,
                           filters=BookingDiscoveryFilters, action_label="Book a time"))
    register_clone_extension("bookings", "website", copy_page)
