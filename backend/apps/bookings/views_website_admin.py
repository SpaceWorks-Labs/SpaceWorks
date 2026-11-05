"""Separate private editor/preview; public asset endpoints cannot preview drafts."""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.apiclients.throttling import ClientTierRateThrottle
from apps.evidence.storage import StorageUnavailable
from apps.hardware_requests.exceptions import ErrorSerializer
from . import booking_authority
from .admission import require_feature
from .models_website import BookingResourcePageAsset
from .serializers_website import (
    BookingWebsiteSerializer, BookingWebsiteContentInput, BookingWebsiteReleaseInput,
    BookingWebsiteAssetInput, BookingWebsiteAssetSerializer,
)
from .services_website import save_content, set_release
from .services_website_assets import upload_asset, delete_asset, image_response
from .website_projection import project

ERRORS = {code: OpenApiResponse(ErrorSerializer, description=label) for code, label in (
    (400, "Invalid content or stale revision."), (401, "Sign in required."),
    (403, "Missing resource permission or wrong origin."), (404, "Unknown or out-of-scope resource/image, or the feature is turned off."),
    (429, "Rate limit exceeded."), (423, "Tenant frozen."), (503, "Storage or write gate unavailable."),
)}


def target_for(request, pk, permission="view"):
    space = booking_authority.get_space(request.user, pk, permission)
    require_feature(space, "bookings.website")
    return space


def payload(space):
    return BookingWebsiteSerializer(project(space)).data


class StaffWebsiteBase(APIView):
    permission_classes = [IsActiveStaff]
    throttle_classes = [ClientTierRateThrottle]
    throttle_scope = "public_read"

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "private, no-store"
        from django.utils.cache import patch_vary_headers
        patch_vary_headers(response, ("Authorization", "Cookie"))
        return response


class BookingWebsiteView(StaffWebsiteBase):
    @extend_schema(tags=["Booking website"], responses={200: BookingWebsiteSerializer, **ERRORS})
    def get(self, request, pk):
        # A scanner/roster grant does not confer access to unreleased editorial data.
        space = target_for(request, pk)
        if not (booking_authority.can(request.user, space, "edit_details")
                or booking_authority.can(request.user, space, "publish_page")):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied()
        return Response(payload(space))

    @extend_schema(tags=["Booking website"], request=BookingWebsiteContentInput,
                   responses={200: BookingWebsiteSerializer, **ERRORS})
    def put(self, request, pk):
        space = save_content(target_for(request, pk, "edit_details"), actor=request.user, data=request.data)
        return Response(payload(space))


class BookingWebsiteReleaseView(StaffWebsiteBase):
    @extend_schema(tags=["Booking website"], request=BookingWebsiteReleaseInput,
                   responses={200: BookingWebsiteSerializer, **ERRORS})
    def post(self, request, pk):
        space = set_release(target_for(request, pk, "publish_page"), actor=request.user, data=request.data)
        return Response(payload(space))


class BookingWebsiteAssetView(StaffWebsiteBase):
    parser_classes = [MultiPartParser]

    def initialize_request(self, request, *args, **kwargs):
        from apps.makerspaces.website_uploads import WebsiteUploadLimit
        request.upload_handlers.insert(0, WebsiteUploadLimit(request))
        return super().initialize_request(request, *args, **kwargs)

    @extend_schema(tags=["Booking website"], request=BookingWebsiteAssetInput,
                   responses={201: BookingWebsiteAssetSerializer, **ERRORS})
    def post(self, request, pk):
        space = target_for(request, pk, "edit_details")
        data = BookingWebsiteAssetInput(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            asset = upload_asset(space, actor=request.user, **data.validated_data)
        except StorageUnavailable:
            return Response({"detail": "Image storage is unavailable."}, status=503)
        return Response(BookingWebsiteAssetSerializer(asset).data, status=201)


class BookingWebsiteAssetDetailView(StaffWebsiteBase):
    @extend_schema(tags=["Booking website"], responses={(200, "image/webp"): OpenApiResponse(bytes, description="Private no-store WebP preview."), **ERRORS})
    def get(self, request, pk, asset_id):
        space = target_for(request, pk, "edit_details")
        asset = get_object_or_404(BookingResourcePageAsset.objects.select_related("page__space__makerspace"),
                                  page__space=space, pk=asset_id)
        return image_response(asset)

    @extend_schema(tags=["Booking website"], responses={204: None, **ERRORS})
    def delete(self, request, pk, asset_id):
        delete_asset(target_for(request, pk, "edit_details"), asset_id, actor=request.user)
        return Response(status=204)
