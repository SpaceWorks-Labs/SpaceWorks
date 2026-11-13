"""Allow-list public projections share one live visibility boundary."""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.apiclients.throttling import ClientTierRateThrottle
from apps.hardware_requests.exceptions import ErrorSerializer
from .serializers_website import PublicBookingResourceSerializer, BookingWebsiteSerializer
from .services_website_assets import image_response
from .website_projection import detail, project
from .website_visibility import resolve, visible_page

ERRORS = {code: OpenApiResponse(ErrorSerializer, description=text) for code, text in (
    (404, "Unknown, private, inactive, disabled or unreleased content."),
    (429, "Rate limit exceeded."), (503, "Image storage unavailable."),
)}


class PublicWebsiteBase(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ClientTierRateThrottle]
    throttle_scope = "public_read"
    # Cache-Control: no-store is set by config.request_id (makerspaces.confirmation_privacy).


class PublicBookingResourceView(PublicWebsiteBase):
    @extend_schema(tags=["Public booking website"], auth=[], responses={200: PublicBookingResourceSerializer, **ERRORS})
    def get(self, request, makerspace_slug, public_token):
        return Response(PublicBookingResourceSerializer(detail(resolve(makerspace_slug, public_token))).data)


class PublicBookingWebsiteView(PublicWebsiteBase):
    @extend_schema(tags=["Public booking website"], auth=[], responses={200: BookingWebsiteSerializer, **ERRORS})
    def get(self, request, makerspace_slug, public_token):
        return Response(BookingWebsiteSerializer(project(resolve(makerspace_slug, public_token), public=True)).data)


class PublicBookingWebsiteImageView(PublicWebsiteBase):
    @extend_schema(tags=["Public booking website"], auth=[], responses={(200, "image/webp"): OpenApiResponse(bytes, description="Live-gated released WebP image."), **ERRORS})
    def get(self, request, makerspace_slug, public_token, asset_id):
        page = visible_page(resolve(makerspace_slug, public_token))
        asset = get_object_or_404(page.assets.filter(
            bookingresourcepagesection__page=page,
            bookingresourcepagesection__visibility="published").distinct(), pk=asset_id)
        return image_response(asset)
