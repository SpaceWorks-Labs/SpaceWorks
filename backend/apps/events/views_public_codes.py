"""Short event identity resolves its venue server-side before applying live gates.

Two shapes share one gate: the 36-character UUID `public_token` and the 7-character
base62 short code. A UUID always contains hyphens, so the shapes never overlap.
"""

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from apps.makerspaces.public_profile_views import PublicProfileBase
from apps.makerspaces.public_page_access import canonical_origin, require_scope
from .serializers_public import PublicEventSerializer
from .website_visibility import resolve

NOINDEX = "noindex, nofollow"


class PublicEventCodeSerializer(PublicEventSerializer):
    canonical_url = serializers.CharField()
    content_url = serializers.CharField()


def robots(response, event):
    """Unlisted events are reachable by link but never indexed."""
    if event.listing != event.Listing.LISTED:
        response["X-Robots-Tag"] = NOINDEX
    return response


def event_code_response(request, event, address):
    require_scope("makerspace", event.makerspace, request)
    event.canonical_url = f"{canonical_origin(event.makerspace)}/e/{address}"
    event.content_url = f"/api/v1/public/{event.makerspace.slug}/events/{event.public_token}/"
    return robots(Response(PublicEventCodeSerializer(event, context={"request": request}).data), event)


def event_for(public_token=None, code=None):
    if code is not None:
        from .short_links import resolve_code
        return resolve_code(code)
    return resolve(None, public_token)


def api_client_target(request, view_name, kwargs):
    """The signed-client target for both code shapes: the venue, behind the live gate."""
    if view_name == "public-event-short-code":
        event = event_for(code=kwargs.get("code"))
    else:
        event = event_for(public_token=kwargs.get("public_token"))
    require_scope("makerspace", event.makerspace, request)
    return event.makerspace, True


class PublicEventCodeView(PublicProfileBase):
    @extend_schema(tags=["Public events"], auth=[], responses={200: PublicEventCodeSerializer,
        404: OpenApiResponse(description="Unknown, hidden, disabled or expired event.")})
    def get(self, request, public_token):
        self.cache_headers()
        return event_code_response(request, resolve(None, public_token), public_token)


class PublicEventShortCodeView(PublicProfileBase):
    throttle_scope = "event_short_link"

    @extend_schema(
        tags=["Public events"], auth=[],
        parameters=[OpenApiParameter("X-SW-Visit", str, OpenApiParameter.HEADER, required=False,
                                     description="Send `1` on the first resolve of a page load to count one visit.")],
        responses={200: PublicEventCodeSerializer,
                   404: OpenApiResponse(description="Unknown, retired, hidden, offline, disabled or ended event."),
                   429: OpenApiResponse(description="Rate limit exceeded (30 per minute per client).")})
    def get(self, request, code):
        self.cache_headers()
        event = event_for(code=code)
        response = event_code_response(request, event, code)
        from .short_links import record_visit
        record_visit(event, request)
        return response


class PublicEventCodeShareView(PublicProfileBase):
    @extend_schema(tags=["Public events"], auth=[], responses={
        (200, "text/html"): OpenApiResponse(str, description="Live-gated short-event metadata."),
        404: OpenApiResponse(description="Unavailable event.")})
    def get(self, request, public_token=None, code=None):
        from .website_adapter import share_card
        from apps.makerspaces.website_serving import share_response
        from dataclasses import replace
        self.cache_headers()
        event = event_for(public_token, code)
        require_scope("makerspace", event.makerspace, request)
        from .share_cards import with_share_image
        data = replace(share_card(event), url=f"{canonical_origin(event.makerspace)}/e/{code or event.public_token}")
        response = share_response(with_share_image(data, event))
        response["Cache-Control"] = "no-store"
        return robots(response, event)


class PublicEventCoverShareView(PublicProfileBase):
    @extend_schema(tags=["Public events"], auth=[], responses={
        200: OpenApiResponse(bytes, description="Current released cover WebP; private, no-store."),
        404: OpenApiResponse(description="Unavailable event or released cover."),
        429: OpenApiResponse(description="Rate limit exceeded."),
        503: OpenApiResponse(description="Image storage is unavailable.")})
    def get(self, request, public_token=None, code=None):
        from django.http import Http404
        from .website_visibility import visible_page
        from .views_website_public import released_image_response
        self.cache_headers()
        event = event_for(public_token, code)
        require_scope("makerspace", event.makerspace, request)
        page = visible_page(event)
        document = page.published_revision.document
        editorial = document.get("editorial_document", {})
        if (not document.get("section_enabled", {}).get("HERO", True)
                or editorial.get("cover_mode") != "asset"):
            raise Http404
        return robots(released_image_response(page, editorial["cover_asset_id"]), event)
