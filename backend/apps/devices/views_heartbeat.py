"""The signed heartbeat: the one 7a route a device calls with its own key.

Release 2 L10 extends it: an optional ``{"status_snapshot": {...}}`` body carries a
printer's bounded status (``services_integration_status``). An empty body behaves
exactly as before; the snapshot never fails the heartbeat it rides on.
"""

from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.devices.authentication import DeviceAuthentication
from apps.devices.errors import DeviceErrorSerializer
from apps.devices.permissions import DeviceRoutePermission
from apps.devices.serializers_identity import DeviceIdentitySerializer
from apps.devices.serializers_integrations import HeartbeatResponseSerializer, HeartbeatSerializer
from apps.devices.services_integration_status import store_snapshot
from apps.devices.services_requests import record_heartbeat


@extend_schema(tags=["Device protocol"])
class DeviceHeartbeatView(APIView):
    authentication_classes = [DeviceAuthentication]
    permission_classes = [DeviceRoutePermission]

    @extend_schema(
        summary="Report device activity and recover an offline device (signed request)",
        request=HeartbeatSerializer,
        responses={
            200: HeartbeatResponseSerializer,
            **{
                code: OpenApiResponse(DeviceErrorSerializer, description=text)
                for code, text in (
                    (400, "An invalid status snapshot (sizes, kinds, unknown fields)."),
                    (404, "The module is turned off."),
                    (401, "Missing, malformed, stale, replayed or invalid signature."),
                    (403, "Device not allowed on this route, revoked or tenant unavailable."),
                    (423, "Tenant frozen for migration."),
                )
            },
        },
    )
    def post(self, request):
        snapshot = None
        if request.body:
            serializer = HeartbeatSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            snapshot = serializer.validated_data.get("status_snapshot")
        now = timezone.now()
        device = record_heartbeat(request.user, now=now)
        data = DeviceIdentitySerializer(device).data
        if snapshot is not None:
            data["status_snapshot"] = store_snapshot(request.user, snapshot, now=now)
        return Response(data)
