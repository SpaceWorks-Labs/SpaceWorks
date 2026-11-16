"""Machine-integration routes (release 2 L10): foundation only, off by default (#76).

Every route answers 404 unless the makerspace has `machines.integrations`. Device routes
are signed (protocol v1) and listed in the device route registry; staff routes need
MANAGE_DEVICES plus a machine scope that covers the type.
"""
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.devices.errors import DeviceErrorSerializer
from apps.devices.serializers_integrations import (
    IntegrationStatusSerializer, JobReportSerializer, QueueSerializer, TypeIntegrationCreateSerializer,
    TypeIntegrationSerializer, TypeIntegrationUpdateSerializer,
)
from apps.devices.serializers_printers import JobSerializer
from apps.devices.services_integration_bindings import (
    create_integration, delete_integration, integration_status, machine_type_for, scoped_integration,
    update_integration,
)
from apps.devices.integration_access import require_integrations
from apps.devices.services_integration_reports import job_queue, report_job
from apps.devices.views_printer_common import SignedDeviceView

OFF = "Not found: the `machines.integrations` capability is off (the default), or the target is outside scope."
DEVICE_ERRORS = {code: OpenApiResponse(DeviceErrorSerializer, description=text) for code, text in (
    (400, "Invalid payload."), (401, "Authentication/signature/replay refused."),
    (403, "Device revoked or tenant unavailable."), (404, OFF + " Also: the device is not an active printer "
                                                      "bound to a machine whose type has an enabled printer agent."),
    (409, "Report conflicts with the job: job_unknown, job_conflict, job_not_started, job_not_reported_started, "
          "or an immutable terminal report changed."),
    (423, "Tenant frozen for migration."))}
STAFF_ERRORS = {code: OpenApiResponse(DeviceErrorSerializer, description=text) for code, text in (
    (400, "Invalid payload or integration_kind_unsupported."), (401, "Not signed in."),
    (403, "Missing MANAGE_DEVICES or the machine type is outside your scope."), (404, OFF),
    (409, "integration_exists: the type already has this integration."))}


class DeviceIntegrationQueueView(SignedDeviceView):
    @extend_schema(tags=["Device protocol"], summary="Pull approved jobs for the device's machine type (signed)",
                   request=None, responses={200: QueueSerializer, **DEVICE_ERRORS})
    def get(self, request):
        return Response(QueueSerializer(job_queue(request.user)).data)


class DeviceIntegrationJobReportView(SignedDeviceView):
    @extend_schema(tags=["Device protocol"], summary="Report a job started, completed or failed (signed)",
                   request=JobReportSerializer, responses={200: JobSerializer, **DEVICE_ERRORS})
    def post(self, request, pk):
        require_integrations(request.user.makerspace_id)
        serializer = JobReportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(JobSerializer(report_job(request.user, pk, serializer)).data)


class TypeIntegrationListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Devices"], summary="List a machine type's integration bindings",
                   responses={200: TypeIntegrationSerializer(many=True), **STAFF_ERRORS})
    def get(self, request, makerspace_id, type_id):
        machine_type = machine_type_for(request.user, makerspace_id, type_id)
        rows = machine_type.integrations.filter(makerspace_id=makerspace_id)
        return Response(TypeIntegrationSerializer(rows, many=True).data)

    @extend_schema(tags=["Devices"], summary="Bind an integration kind to a machine type (created disabled)",
                   request=TypeIntegrationCreateSerializer, responses={201: TypeIntegrationSerializer, **STAFF_ERRORS})
    def post(self, request, makerspace_id, type_id):
        machine_type = machine_type_for(request.user, makerspace_id, type_id)
        serializer = TypeIntegrationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = create_integration(request.user, makerspace_id, machine_type, **serializer.validated_data)
        return Response(TypeIntegrationSerializer(row).data, status=201)


class TypeIntegrationDetailView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Devices"], summary="Read one integration binding",
                   responses={200: TypeIntegrationSerializer, **STAFF_ERRORS})
    def get(self, request, pk):
        return Response(TypeIntegrationSerializer(scoped_integration(request.user, pk)).data)

    @extend_schema(tags=["Devices"], summary="Enable, disable or re-version an integration binding",
                   request=TypeIntegrationUpdateSerializer, responses={200: TypeIntegrationSerializer, **STAFF_ERRORS})
    def patch(self, request, pk):
        serializer = TypeIntegrationUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(TypeIntegrationSerializer(update_integration(request.user, pk, serializer.validated_data)).data)

    @extend_schema(tags=["Devices"], summary="Remove an integration binding", request=None,
                   responses={204: None, **STAFF_ERRORS})
    def delete(self, request, pk):
        delete_integration(request.user, pk)
        return Response(status=204)


class TypeIntegrationStatusView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Devices"], summary="Read-only status of the printers bound to this machine type",
                   responses={200: IntegrationStatusSerializer(many=True), **STAFF_ERRORS})
    def get(self, request, makerspace_id, type_id):
        machine_type = machine_type_for(request.user, makerspace_id, type_id)
        rows = integration_status(makerspace_id, machine_type)
        return Response(IntegrationStatusSerializer(rows, many=True).data)
