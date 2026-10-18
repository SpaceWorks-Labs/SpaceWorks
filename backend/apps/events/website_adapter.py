"""Concrete typed event adapter for the always-present public projection engine."""

from rest_framework.fields import DateTimeField
from django.utils import timezone

from apps.inventory import public_image_storage
from apps.makerspaces.website_serving import PublicCard
from apps.makerspaces.website_directory import public_url
from apps.makerspaces.website_visibility import WebsiteAdapter, register, website_enabled

from .capacity import availability_label, confirmed_occupancy
from .models import Event
from .organization_audience import AUDIENCE, audience_projection, audience_projections
from .website_visibility import resolve, discover_events, visible_page


def published_page(event):
    """Use discovery's joined page/revision; never resolve detail per card."""
    page = getattr(event, "website_page", None)
    if page is None and event.series_id:
        page = getattr(event.series, "website_page", None)
    if (page and page.released and page.published_revision_id
            and event.is_public and event.status == Event.Status.PUBLISHED
            and event.ends_at >= timezone.now()):
        from apps.makerspaces.capability_eligibility import configuration_feature_enabled
        enabled = (configuration_feature_enabled(event.makerspace, "events.website")
                   if getattr(event, "website_host_servable", False)
                   else website_enabled(event, "events"))
        if enabled:
            return page
    return None


def card(event: Event, *, audience_label=None, cover_assets=None) -> PublicCard:
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
    from apps.makerspaces.public_page_access import canonical_origin
    image_url, image_alt, description = public_image_storage.public_url(image_key) or None, "", event.description[:300]
    published = published_page(event)
    if published:
        document = published.published_revision.document
        editorial = document.get("editorial_document", {})
        if document.get("section_enabled", {}).get("HERO", True):
            description = document.get("tagline") or description
            if editorial.get("cover_mode") == "asset":
                asset = (cover_assets.get(editorial["cover_asset_id"]) if cover_assets is not None
                         else published.assets.get(pk=editorial["cover_asset_id"]))
                if asset is None or asset.page_id != published.pk:
                    from django.http import Http404
                    raise Http404
                image_url = (f"{canonical_origin(event.makerspace)}/api/v1/public/{event.makerspace.slug}/events/"
                             f"{event.public_token}/website/assets/{asset.pk}/")
                image_alt = asset.alt_text
            elif editorial.get("cover_mode") == "none":
                image_url = None
    return PublicCard(
        title=event.title, description=description[:300],
        url=public_url(event.makerspace, "events", event.public_token),
        image_url=image_url, image_alt=image_alt,
        date=DateTimeField().to_representation(event.starts_at), location=event.location,
        availability=availability_label(event), audience_label=audience_label,
        registration_count=confirmed_occupancy(event) if event.show_registration_count else None,
        makerspace_name=event.makerspace.name,
        revision=f"{event.makerspace_id}:{event.pk}:{event.updated_at.isoformat()}:{revision}:{event.makerspace.updated_at.isoformat()}",
    )


def cards(events: list[Event]) -> list[PublicCard]:
    # Only organization-audience cards need attribution; no tickets, account
    # eligibility, feature projections or full detail serializers on this path.
    projections = audience_projections([event for event in events if event.registration_audience == AUDIENCE])
    from .models_website import EventPageAsset
    cover_ids = set()
    for event in events:
        page = published_page(event)
        if page:
            document = page.published_revision.document
            editorial = document.get("editorial_document", {})
            if (document.get("section_enabled", {}).get("HERO", True)
                    and editorial.get("cover_mode") == "asset"):
                cover_ids.add(editorial["cover_asset_id"])
    cover_assets = EventPageAsset.objects.in_bulk(cover_ids) if cover_ids else {}
    return [card(event, audience_label=projections.get(
        (event._meta.label, event.pk), {},
    ).get("audience_label", ""), cover_assets=cover_assets) for event in events]


def share_card(event):
    """Crawlers cannot send API-client headers; cover bytes still repeat live gates."""
    from dataclasses import replace
    from apps.makerspaces.public_page_access import canonical_origin
    result = card(event)
    page = published_page(event)
    if page:
        document = page.published_revision.document
        if (document.get("section_enabled", {}).get("HERO", True)
                and document.get("editorial_document", {}).get("cover_mode") == "asset"):
            return replace(result, image_url=f"{canonical_origin(event.makerspace)}/share/e/{event.public_token}/cover/")
    return result


def register_website():
    register(WebsiteAdapter(kind="events", module="events", resolve=resolve, discover=discover_events, card=card, page=visible_page, cards=cards, share_card=share_card))
