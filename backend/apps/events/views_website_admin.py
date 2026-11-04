"""Staff editor surfaces use event predicates, never tenant-wide grant expansion."""

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.apiclients.throttling import ClientTierRateThrottle
from apps.evidence.storage import StorageUnavailable
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces import website_assets

from . import event_authority
from .event_permissions import VIEW, EDIT_DETAILS
from .models import EventSeries
from .models_website import EventPage
from .serializers_website import (
    WebsiteContentInput, WebsiteSerializer, WebsiteReleaseInput, WebsiteDelayInput,
    WebsiteAssetInput, WebsiteAssetSerializer,
)
from .services_website import save_content, set_release, set_delay
from .services_website_assets import upload_asset, delete_asset
from .website_projection import project

ERRORS = {code: OpenApiResponse(ErrorSerializer, description=label) for code, label in (
    (400, "Invalid content, stale revision, disabled feature or terminal event."),
    (401, "Sign in required."), (403, "Missing event permission or wrong staff origin."),
    (404, "Unknown or out-of-scope event/page/image."), (429, "Rate limit exceeded."),
    (503, "Private image storage is unavailable."),
)}


def target_for(request, pk, series=False, permission=VIEW):
    from apps.makerspaces.public_page_authority import reject_platform
    reject_platform(request.user, tenant=True)
    target = event_authority.get_event(request.user, pk, permission, series=series)
    from .feature_gates import require_feature
    require_feature(target, "events.website")
    return target


def payload(request, target):
    prefix = "event-series" if isinstance(target, EventSeries) else "events"
    result = project(target, image_url=lambda asset: f"/api/v1/admin/{prefix}/{target.pk}/website/assets/{asset}")
    from .event_permissions import PUBLISH_SCHEDULE
    result["capabilities"] = {"can_edit_details": event_authority.can(request.user, target, EDIT_DETAILS),
                              "can_publish_schedule": event_authority.can(request.user, target, PUBLISH_SCHEDULE)}
    return WebsiteSerializer(result).data


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


class EventWebsiteView(StaffWebsiteBase):
    @extend_schema(tags=["Event website"], responses={200: WebsiteSerializer, **ERRORS})
    def get(self, request, pk, series=False):
        return Response(payload(request, target_for(request, pk, series)))

    @extend_schema(tags=["Event website"], request=WebsiteContentInput, responses={200: WebsiteSerializer, **ERRORS})
    def put(self, request, pk, series=False):
        target = save_content(target_for(request, pk, series), actor=request.user, data=request.data)
        return Response(payload(request, target))


class EventWebsiteReleaseView(StaffWebsiteBase):
    @extend_schema(tags=["Event website"], request=WebsiteReleaseInput, responses={200: WebsiteSerializer, **ERRORS})
    def post(self, request, pk, series=False):
        data = WebsiteReleaseInput(data=request.data)
        data.is_valid(raise_exception=True)
        target = target_for(request, pk, series)
        set_release(target, actor=request.user, **data.validated_data)
        return Response(payload(request, target))


class EventWebsiteDelayView(StaffWebsiteBase):
    @extend_schema(tags=["Event website"], request=WebsiteDelayInput, responses={200: WebsiteSerializer, **ERRORS})
    def post(self, request, pk, slug, series=False):
        data = WebsiteDelayInput(data=request.data)
        data.is_valid(raise_exception=True)
        target = set_delay(target_for(request, pk, series), slug, actor=request.user,
                           minutes=data.validated_data["delay_minutes"],
                           revision=data.validated_data.get("revision"), session_id=data.validated_data.get("session_id"))
        return Response(payload(request, target))


class EventWebsiteAssetView(StaffWebsiteBase):
    parser_classes = [MultiPartParser]

    def initialize_request(self, request, *args, **kwargs):
        from apps.makerspaces.website_uploads import WebsiteUploadLimit
        request.upload_handlers.insert(0, WebsiteUploadLimit(request))
        return super().initialize_request(request, *args, **kwargs)

    @extend_schema(tags=["Event website"], request=WebsiteAssetInput, responses={201: WebsiteAssetSerializer, **ERRORS})
    def post(self, request, pk, series=False):
        target = target_for(request, pk, series, EDIT_DETAILS)
        data = WebsiteAssetInput(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            asset = upload_asset(target, actor=request.user, **data.validated_data)
        except StorageUnavailable:
            return Response({"detail": "Image storage is unavailable."}, status=503)
        return Response(WebsiteAssetSerializer(asset).data, status=201)


class EventWebsiteAssetDetailView(StaffWebsiteBase):
    @extend_schema(tags=["Event website"], responses={200: OpenApiResponse(bytes, description="Private WebP image; no-store."), **ERRORS})
    def get(self, request, pk, asset_id, series=False):
        target = target_for(request, pk, series, EDIT_DETAILS)
        from .website_visibility import effective_page
        page = EventPage.objects.filter(series=target).first() if series else effective_page(target)
        asset = get_object_or_404(page.assets if page else EventPage.objects.none(), pk=asset_id)
        return image_response(asset)

    @extend_schema(tags=["Event website"], responses={204: None, **ERRORS})
    def delete(self, request, pk, asset_id, series=False):
        delete_asset(target_for(request, pk, series, EDIT_DETAILS), asset_id, actor=request.user)
        return Response(status=204)


def image_response(asset):
    from apps.makerspaces.website_serving import private_image_response
    if not website_assets.owns(asset.object_key, "events", asset.page.makerspace_id, asset.page_id, asset=asset):
        from django.http import Http404
        raise Http404
    return private_image_response(asset.object_key)
