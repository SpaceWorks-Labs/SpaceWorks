"""Staff and member routes for the media/data capabilities (decision 321).

Staff: MANAGE_DEVICES in the space plus the machine scope, behind `machines.integrations` and the capability's child
switch (404 when off). Member: the job owner reads the artifacts and detections of THEIR job only.
"""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.devices import services_adapter_artifacts as artifacts
from apps.devices import services_adapter_config as config
from apps.devices import services_adapter_detect as detect
from apps.devices import services_adapter_history as history
from apps.devices import services_adapter_media as media
from apps.devices.adapter_access import DIAGNOSTICS_SWITCH, scoped_binding
from apps.devices.openapi_adapter_staff import RESPONSES as DOC, page
from apps.devices.serializers_adapter_media import (ArtifactSerializer, ConfigPushSerializer, ConfigVersionSerializer,
                                                    DetectionSerializer, OwnerDetectionSerializer, TalkSerializer)
from apps.devices.services_adapter_commands import enqueue
from apps.devices.throttles import WATCH_RELAY_THROTTLES
from apps.devices.views_adapter_admin import ERRORS, TAG

MEMBER_TAG = "Device adapter media (job owner)"
_KIND = OpenApiParameter("kind", OpenApiTypes.STR)
_REQUEST = OpenApiParameter("service_request_id", OpenApiTypes.INT)


def _page(request, queryset, serializer):
    paginator = PageNumberPagination()
    page = paginator.paginate_queryset(queryset, request, view=None)
    return paginator.get_paginated_response(serializer(page, many=True).data)


class BindingArtifactListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="Artifacts a binding uploaded (timelapses, previews, snapshots, bundles)",
                   parameters=[_KIND, _REQUEST], responses={200: page("AdapterArtifactPage", ArtifactSerializer), **ERRORS})
    def get(self, request, pk):
        return _page(request, artifacts.staff_list(request.user, pk, request.query_params), ArtifactSerializer)


class ArtifactUrlView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="Short-lived private URL for one artifact (audio and bundles are audited)",
                   responses={200: DOC["artifact_url"], **ERRORS})
    def get(self, request, pk):
        return Response(artifacts.staff_url(request.user, pk))


class BindingDetectionListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="Detections a binding reported (failure, fire, smoke, person...)",
                   parameters=[_KIND], responses={200: page("AdapterDetectionPage", DetectionSerializer), **ERRORS})
    def get(self, request, pk):
        return _page(request, detect.staff_list(request.user, pk, request.query_params), DetectionSerializer)


class BindingTelemetryView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="Telemetry history for charts (raw, 1-minute or 15-minute points)",
                   parameters=[OpenApiParameter("series", OpenApiTypes.STR), OpenApiParameter("since", OpenApiTypes.DATETIME),
                               OpenApiParameter("until", OpenApiTypes.DATETIME),
                               OpenApiParameter("resolution", OpenApiTypes.INT, description="0, 60 or 900; default automatic.")],
                   responses={200: DOC["telemetry"], **ERRORS})
    def get(self, request, pk):
        return Response(history.read(request.user, pk, request.query_params))


class BindingLogBundleView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="Ask the adapter to upload a log bundle (private, seven days, size-capped)",
                   request=None, responses={201: DOC["command_queued"], **ERRORS})
    def post(self, request, pk):
        scoped_binding(request.user, pk, child=DIAGNOSTICS_SWITCH)
        row = enqueue(request.user, pk, "diagnostics", "log_bundle",
                      {"max_bytes": 10 * 2 ** 20, "since_seconds": 6 * 3600})
        return Response({"command_id": str(row.pk), "status": row.status}, status=201)


class AdapterConfigVersionsView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="The last config versions pushed to an adapter, with acknowledgements",
                   responses={200: ConfigVersionSerializer(many=True), **ERRORS})
    def get(self, request, pk):
        return Response(ConfigVersionSerializer(config.history(request.user, pk), many=True).data)

    @extend_schema(tags=[TAG], summary="Push a new config version (no secrets; 16 KiB; audited)",
                   request=ConfigPushSerializer, responses={201: ConfigVersionSerializer, **ERRORS})
    def post(self, request, pk):
        serializer = ConfigPushSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(ConfigVersionSerializer(config.push(request.user, pk, serializer.validated_data["config"])).data,
                        status=201)


# --- member (job owner) -----------------------------------------------------------------------------------------
class MemberArtifactListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=[MEMBER_TAG], summary="Thumbnails, previews and timelapses of your own machine job",
                   responses={200: page("MemberAdapterArtifactPage", ArtifactSerializer), **ERRORS})
    def get(self, request, request_id):
        return _page(request, artifacts.owner_list(request.user, request_id), ArtifactSerializer)


class MemberArtifactUrlView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=[MEMBER_TAG], summary="Short-lived private URL for an artifact of your own job",
                   responses={200: DOC["artifact_url"], **ERRORS})
    def get(self, request, pk):
        return Response(artifacts.owner_url(request.user, pk))


class MemberDetectionListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=[MEMBER_TAG], summary="Detections on the machine running your own job",
                   responses={200: page("MemberAdapterDetectionPage", OwnerDetectionSerializer), **ERRORS})
    def get(self, request, request_id):
        return _page(request, detect.owner_list(request.user, request_id), OwnerDetectionSerializer)


class ViewerTalkView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = WATCH_RELAY_THROTTLES

    @extend_schema(tags=[MEMBER_TAG], summary="Push-to-talk press or release on a staff watch (audited)",
                   request=TalkSerializer, responses={201: DOC["talk"], **ERRORS})
    def post(self, request, pk):
        serializer = TalkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(media.viewer_talk(request.user, pk, serializer.validated_data["active"]), status=201)
