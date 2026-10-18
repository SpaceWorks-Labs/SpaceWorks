"""Short event identity resolves its venue server-side before applying live gates."""

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from apps.makerspaces.public_profile_views import PublicProfileBase
from apps.makerspaces.public_page_access import canonical_origin, require_scope
from .serializers_public import PublicEventSerializer
from .website_visibility import resolve


class PublicEventCodeSerializer(PublicEventSerializer):
    canonical_url = serializers.CharField()
    content_url = serializers.CharField()


class PublicEventCodeView(PublicProfileBase):
    @extend_schema(tags=["Public events"], auth=[], responses={200: PublicEventCodeSerializer,
        404: OpenApiResponse(description="Unknown, hidden, disabled or expired event.")})
    def get(self, request, public_token):
        self.cache_headers()
        event = resolve(None, public_token)
        require_scope("makerspace", event.makerspace, request)
        event.canonical_url = f"{canonical_origin(event.makerspace)}/e/{event.public_token}"
        event.content_url = f"/api/v1/public/{event.makerspace.slug}/events/{event.public_token}/"
        return Response(PublicEventCodeSerializer(event, context={"request": request}).data)


class PublicEventCodeShareView(PublicProfileBase):
    @extend_schema(tags=["Public events"], auth=[], responses={
        (200, "text/html"): OpenApiResponse(str, description="Live-gated short-event metadata."),
        404: OpenApiResponse(description="Unavailable event.")})
    def get(self, request, public_token):
        from .website_adapter import share_card
        from apps.makerspaces.website_serving import share_response
        from dataclasses import replace
        self.cache_headers()
        event = resolve(None, public_token)
        require_scope("makerspace", event.makerspace, request)
        data = replace(share_card(event), url=f"{canonical_origin(event.makerspace)}/e/{event.public_token}")
        response = share_response(data)
        response["Cache-Control"] = "no-store"
        return response


class PublicEventCoverShareView(PublicProfileBase):
    @extend_schema(tags=["Public events"], auth=[], responses={
        200: OpenApiResponse(bytes, description="Current released cover WebP; private, no-store."),
        404: OpenApiResponse(description="Unavailable event or released cover."),
        429: OpenApiResponse(description="Rate limit exceeded."),
        503: OpenApiResponse(description="Image storage is unavailable.")})
    def get(self, request, public_token):
        from django.http import Http404
        from .website_visibility import visible_page
        from .views_website_public import released_image_response
        self.cache_headers()
        event = resolve(None, public_token)
        require_scope("makerspace", event.makerspace, request)
        page = visible_page(event)
        document = page.published_revision.document
        editorial = document.get("editorial_document", {})
        if (not document.get("section_enabled", {}).get("HERO", True)
                or editorial.get("cover_mode") != "asset"):
            raise Http404
        return released_image_response(page, editorial["cover_asset_id"])
