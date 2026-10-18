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
        from .website_adapter import card
        from apps.makerspaces.website_serving import share_response
        from dataclasses import replace
        self.cache_headers()
        event = resolve(None, public_token)
        require_scope("makerspace", event.makerspace, request)
        data = replace(card(event), url=f"{canonical_origin(event.makerspace)}/e/{event.public_token}")
        response = share_response(data)
        response["Cache-Control"] = "no-store"
        return response
