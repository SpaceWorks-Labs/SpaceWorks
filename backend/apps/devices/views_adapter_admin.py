"""Staff routes for device adapters under ``/api/v1/admin/`` (the small console, decision 312).

Enrollment (one-time token), revoke and key rotation are the existing device routes
(``admin/makerspace/<id>/devices`` with ``kind: "adapter"``, ``admin/devices/<id>/enrollments|revoke``). These add
the adapter picture, bind/unbind, status, controls and logs. Every route needs MANAGE_DEVICES in the space, the
`machines.integrations` switch (404 off) and, for a machine target, the actor's machine scope. Cross-tenant ids
are 404.
"""
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.devices import services_adapter_admin as admin
from apps.devices import services_adapter_commands as commands
from apps.devices.adapter_access import (
    authorize_staff, scoped_adapter, scoped_binding, visible_binding_ids, visible_rows,
)
from apps.devices.errors import DeviceErrorSerializer
from apps.devices.models import Device
from apps.devices.openapi_adapter_staff import RESPONSES as DOC
from apps.devices.serializers_adapter import (
    BindingCreateSerializer, BindingSerializer, CommandCreateSerializer, CommandSerializer, EventSerializer,
)

TAG = "Device adapters (staff)"
ERRORS = {code: OpenApiResponse(DeviceErrorSerializer, description=text) for code, text in (
    (400, "invalid_payload or a typed adapter code."), (401, "Not signed in."),
    (403, "Missing MANAGE_DEVICES, or the machine is outside your scope."),
    (404, "The `machines.integrations` switch is off, or the target is outside your scope or absent."),
    (409, "A typed conflict (binding_exists, capability_missing, adapter_revoked...)."))}


class AdapterListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="List a makerspace's adapters with capabilities, bindings and status",
                   responses={200: DOC["adapter_list"], **ERRORS})
    def get(self, request, makerspace_id):
        authorize_staff(request.user, makerspace_id)
        devices = Device.objects.filter(makerspace_id=makerspace_id, kind=Device.Kind.ADAPTER).order_by("name", "id")
        return Response({"results": [admin.adapter_summary(device, visible_binding_ids(request.user, device))
                                     for device in devices]})


class AdapterDetailView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="One adapter: profile, bindings and latest status",
                   responses={200: DOC["adapter"], **ERRORS})
    def get(self, request, pk):
        device = scoped_adapter(request.user, pk)
        return Response(admin.adapter_summary(device, visible_binding_ids(request.user, device)))


class AdapterBindingCreateView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="Bind a target (machine, door, location...) to an adapter",
                   request=BindingCreateSerializer, responses={201: BindingSerializer, **ERRORS})
    def post(self, request, pk):
        device = scoped_adapter(request.user, pk)
        serializer = BindingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = admin.bind(request.user, device, **serializer.validated_data)
        return Response(BindingSerializer(row).data, status=201)


class AdapterBindingDetailView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="Read a binding with its latest status",
                   responses={200: DOC["binding_detail"], **ERRORS})
    def get(self, request, pk):
        binding = scoped_binding(request.user, pk)
        data = BindingSerializer(binding).data
        data["status"] = admin.binding_status(binding)
        return Response(data)

    @extend_schema(tags=[TAG], summary="Unbind a target (queued commands expire)", request=None,
                   responses={204: None, **ERRORS})
    def delete(self, request, pk):
        admin.unbind(request.user, scoped_binding(request.user, pk))
        return Response(status=204)


class AdapterBindingCommandView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="Send a control command (pause, resume, cancel, power, unlock...)",
                   request=CommandCreateSerializer, responses={201: CommandSerializer, **ERRORS})
    def post(self, request, pk):
        binding = scoped_binding(request.user, pk)
        serializer = CommandCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = commands.enqueue(request.user, binding.pk, **serializer.validated_data)
        return Response(CommandSerializer(row).data, status=201)


class AdapterCommandListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="Recent commands sent to an adapter (logs)",
                   responses={200: CommandSerializer(many=True), **ERRORS})
    def get(self, request, pk):
        device = scoped_adapter(request.user, pk)
        rows = visible_rows(request.user, device, admin.recent_commands_queryset(device))[:50]
        return Response(CommandSerializer(rows, many=True).data)


class AdapterEventListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="Recent events an adapter reported (logs)",
                   responses={200: EventSerializer(many=True), **ERRORS})
    def get(self, request, pk):
        device = scoped_adapter(request.user, pk)
        rows = visible_rows(request.user, device, admin.recent_events_queryset(device))[:50]
        return Response(EventSerializer(rows, many=True).data)
