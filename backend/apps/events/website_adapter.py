"""Concrete typed event adapter for the always-present public projection engine."""

from rest_framework.fields import DateTimeField

from apps.inventory import public_image_storage
from apps.makerspaces.website_directory import public_url
from apps.makerspaces.website_serving import PublicCard
from apps.makerspaces.website_visibility import WebsiteAdapter, register

from .capacity import availability_label, confirmed_occupancy
from .models import Event
from .organization_audience import AUDIENCE, audience_projection, audience_projections
from .website_visibility import resolve, discover_events, visible_page


def card(event: Event, *, audience_label=None) -> PublicCard:
    # Reverse one-to-one access reuses discovery's select_related cache, including
    # missing pages. Keep service-layer page lookups independent of these caches.
    page = getattr(event, "website_page", None)
    if page is None and event.series_id:
        page = getattr(event.series, "website_page", None)
    revision = f"{page.pk}:{page.revision}:{page.released}" if page else "core"
    if audience_label is None:
        audience_label = audience_projection(event)["audience_label"] if event.registration_audience == AUDIENCE else ""
    image_key = event.image_key
    if event.series_id and "image_key" not in (event.series_override_fields or []):
        image_key = event.series.image_key
    return PublicCard(
        title=event.title, description=event.description[:300],
        url=public_url(event.makerspace, "events", event.public_token),
        image_url=public_image_storage.public_url(image_key) or None,
        date=DateTimeField().to_representation(event.starts_at), location=event.location,
        availability=availability_label(event, reservations=False), audience_label=audience_label,
        registration_count=confirmed_occupancy(event) if event.show_registration_count else None,
        makerspace_name=event.makerspace.name,
        revision=f"{event.makerspace_id}:{event.pk}:{event.updated_at.isoformat()}:{revision}:{event.makerspace.updated_at.isoformat()}",
    )


def cards(events: list[Event]) -> list[PublicCard]:
    # Only organization-audience cards need attribution; no tickets, account
    # eligibility, feature projections or full detail serializers on this path.
    projections = audience_projections([event for event in events if event.registration_audience == AUDIENCE])
    return [card(event, audience_label=projections.get(
        (event._meta.label, event.pk), {},
    ).get("audience_label", "")) for event in events]


def register_website():
    register(WebsiteAdapter(kind="events", module="events", resolve=resolve, discover=discover_events, card=card, page=visible_page, cards=cards))
