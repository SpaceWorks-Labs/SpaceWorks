"""Viewer-side watch routes under ``/api/v1/member/``: the job owner (or the staff member who opened the watch)
relays signaling, reads the latest frame and ends the watch. Only a watch's own viewer reaches it (404 otherwise),
and only while ``machines.integrations.video`` is on."""
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.devices import services_adapter_media as media
from apps.devices.openapi_adapter_staff import REQUESTS as DOC_REQUESTS
from apps.devices.openapi_adapter_staff import RESPONSES as DOC
from apps.devices.serializers_adapter import WatchSerializer
from apps.devices.throttles import WATCH_RELAY_THROTTLES, WATCH_START_THROTTLES
from apps.devices.views_adapter_admin import ERRORS

TAG = "Device adapter watch (viewer)"
AFTER = OpenApiParameter("after", int, description="Return only signals with a sequence number above this.")


class JobOwnerWatchView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = WATCH_START_THROTTLES

    @extend_schema(tags=[TAG], summary="Watch the machine running your in-progress request (audited, five minutes)",
                   request=None, responses={201: WatchSerializer, **ERRORS})
    def post(self, request, request_id):
        return Response(WatchSerializer(media.start_for_job_owner(request.user, request_id)).data, status=201)


class ViewerSignalView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = WATCH_RELAY_THROTTLES

    @extend_schema(tags=[TAG], summary="Read the adapter signaling messages (and optional TURN servers)",
                   parameters=[AFTER], responses={200: DOC["viewer_poll"], **ERRORS})
    def get(self, request, pk):
        after = request.query_params.get("after", "0")
        return Response(media.viewer_poll(request.user, pk, int(after) if after.isdigit() else 0))

    @extend_schema(tags=[TAG], summary="Send an SDP offer/answer or ICE candidate to the adapter",
                   request=DOC_REQUESTS["viewer_signal"], responses={201: DOC["viewer_signal"], **ERRORS})
    def post(self, request, pk):
        return Response(media.viewer_signal(request.user, pk, request.data), status=201)


class ViewerFrameView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = WATCH_RELAY_THROTTLES

    @extend_schema(tags=[TAG], summary="Latest snapshot frame (snapshot fallback; only while watching)",
                   responses={200: DOC["frame"], **ERRORS})
    def get(self, request, pk):
        return Response(media.latest_frame(request.user, pk))


class ViewerEndView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = WATCH_RELAY_THROTTLES

    @extend_schema(tags=[TAG], summary="End a watch you opened", request=None,
                   responses={200: WatchSerializer, **ERRORS})
    def delete(self, request, pk):
        return Response(WatchSerializer(media.viewer_end(request.user, pk)).data)
