"""All enhanced public paths resolve the same current event/page gate."""

from django.http import Http404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.apiclients.throttling import ClientTierRateThrottle
from apps.hardware_requests.exceptions import ErrorSerializer
from .serializers_website import PublicWebsiteSerializer, WebsiteSectionSerializer, WebsiteSessionSerializer
from .website_projection import project_page
from .website_visibility import resolve, visible_page
from .views_website_admin import image_response

ERRORS = {code: OpenApiResponse(ErrorSerializer, description=text) for code, text in (
    (404, "Unknown, hidden, disabled, unreleased or expired website content."),
    (429, "Rate limit exceeded."), (503, "Image storage is unavailable."),
)}


def projection(event, request=None):
    if request:
        from apps.makerspaces.public_page_access import require_scope
        require_scope("makerspace", event.makerspace, request)
    page = visible_page(event)
    base = f"/api/v1/public/{event.makerspace.slug}/events/{event.public_token}/website/assets/"
    return project_page(event, page, public=True, image_url=lambda pk: f"{base}{pk}/", request=request)


def released_image_response(page, asset_id):
    """Serve only a current public reference after the caller resolves the live page."""
    from django.shortcuts import get_object_or_404
    from .website_revision_projection import visible_asset_ids
    if not page.makerspace.public_site_enabled or asset_id not in visible_asset_ids(page.published_revision):
        raise Http404
    return image_response(get_object_or_404(page.assets, pk=asset_id))


class PublicWebsiteBase(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ClientTierRateThrottle]
    throttle_scope = "public_read"
    # Cache-Control: no-store is set by config.request_id (makerspaces.confirmation_privacy).


class PublicEventWebsiteView(PublicWebsiteBase):
    @extend_schema(tags=["Public event website"], auth=[], responses={200: PublicWebsiteSerializer, **ERRORS})
    def get(self, request, makerspace_slug, public_token):
        return Response(PublicWebsiteSerializer(projection(resolve(makerspace_slug, public_token), request)).data)


class PublicEventWebsiteSectionView(PublicWebsiteBase):
    @extend_schema(tags=["Public event website"], auth=[], responses={200: WebsiteSectionSerializer, **ERRORS})
    def get(self, request, makerspace_slug, public_token, slug, section_kind=None):
        rows = projection(resolve(makerspace_slug, public_token), request)["sections"]
        row = next((row for row in rows if row["slug"] == slug and (section_kind is None or row["kind"] == section_kind)), None)
        if row is None:
            raise Http404
        return Response(WebsiteSectionSerializer(row).data)


class PublicEventWebsiteScheduleView(PublicWebsiteBase):
    @extend_schema(tags=["Public event website"], auth=[], responses={200: WebsiteSessionSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_slug, public_token):
        return Response(WebsiteSessionSerializer(projection(resolve(makerspace_slug, public_token), request)["sessions"], many=True).data)


class PublicEventWebsiteSessionView(PublicWebsiteBase):
    @extend_schema(tags=["Public event website"], auth=[], responses={200: WebsiteSessionSerializer, **ERRORS})
    def get(self, request, makerspace_slug, public_token, slug):
        rows = projection(resolve(makerspace_slug, public_token), request)["sessions"]
        row = next((row for row in rows if row["slug"] == slug), None)
        if row is None:
            raise Http404
        return Response(WebsiteSessionSerializer(row).data)


class PublicEventWebsiteImageView(PublicWebsiteBase):
    @extend_schema(tags=["Public event website"], auth=[], responses={200: OpenApiResponse(bytes, description="Released WebP image."), **ERRORS})
    def get(self, request, makerspace_slug, public_token, asset_id):
        event = resolve(makerspace_slug, public_token)
        from apps.makerspaces.public_page_access import require_scope
        require_scope("makerspace", event.makerspace, request)
        page = visible_page(event)
        return released_image_response(page, asset_id)
