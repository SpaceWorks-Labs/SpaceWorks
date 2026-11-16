"""Staff routes: webhook push endpoint of an adapter, and per-machine-type safety profiles (MANAGE_DEVICES)."""
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.devices import services_adapter_profile as profiles
from apps.devices import services_adapter_webhook as push
from apps.devices.openapi_adapter_staff import RESPONSES as DOC
from apps.devices.serializers_adapter import TypeProfileSerializer, WebhookWriteSerializer
from apps.devices.views_adapter_admin import ERRORS, TAG


def _valid(serializer_class, data):
    serializer = serializer_class(data=data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def _hook(hook, secret=None):
    out = {"url": hook.url, "enabled": hook.enabled, "include_data": hook.include_data,
           "secret_version": hook.secret_version, "consecutive_failures": hook.consecutive_failures,
           "disabled_at": hook.disabled_at, "disabled_reason": hook.disabled_reason,
           "last_success_at": hook.last_success_at}
    if secret:
        out["secret"] = secret  # shown exactly once
    return out


class AdapterWebhookView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="Read the adapter's push endpoint (never the secret)",
                   responses={200: DOC["webhook"], **ERRORS})
    def get(self, request, pk):
        return Response(_hook(push.get_webhook(request.user, pk)))

    @extend_schema(tags=[TAG], summary="Create or change the push endpoint; the secret is returned once, on creation",
                   request=WebhookWriteSerializer, responses={200: DOC["webhook"], **ERRORS})
    def put(self, request, pk):
        hook, secret = push.set_webhook(request.user, pk, **_valid(WebhookWriteSerializer, request.data))
        return Response(_hook(hook, secret))

    @extend_schema(tags=[TAG], summary="Disable the push endpoint", request=None, responses={204: None, **ERRORS})
    def delete(self, request, pk):
        push.disable(request.user, pk)
        return Response(status=204)


class AdapterWebhookRotateView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="Rotate the push secret (returned once; the old one stops verifying)",
                   request=None, responses={200: DOC["webhook"], **ERRORS})
    def post(self, request, pk):
        hook, secret = push.rotate(request.user, pk)
        return Response(_hook(hook, secret))


class AdapterWebhookDeliveriesView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="Delivery log of the push endpoint",
                   responses={200: DOC["webhook_deliveries"], **ERRORS})
    def get(self, request, pk):
        return Response({"results": [
            {"id": str(row.pk), "type": row.event_type, "status": row.status, "attempts": row.attempts,
             "last_status_code": row.last_status_code, "last_error": row.last_error, "created_at": row.created_at,
             "delivered_at": row.delivered_at} for row in push.recent_deliveries(request.user, pk)]})


class AdapterTypeProfileView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="Safety defaults for adapter bindings on a machine type",
                   responses={200: DOC["type_profile"], **ERRORS})
    def get(self, request, makerspace_id, machine_type_id):
        return Response(profiles.get_profile(request.user, makerspace_id, machine_type_id))

    @extend_schema(tags=[TAG], summary="Set the machine type's safety defaults (idle auto-off, area clear, max session, "
                   "filter interlock); bindings may override", request=TypeProfileSerializer,
                   responses={200: DOC["type_profile"], **ERRORS})
    def put(self, request, makerspace_id, machine_type_id):
        data = dict(_valid(TypeProfileSerializer, request.data))
        return Response(profiles.set_profile(request.user, makerspace_id, machine_type_id, data))
