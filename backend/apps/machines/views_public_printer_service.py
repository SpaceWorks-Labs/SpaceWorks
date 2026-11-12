from types import SimpleNamespace
import uuid

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.apiclients.throttling import ClientTierRateThrottle
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.machines.models import MachineServiceRequest
from apps.machines.public_printer_service import public_pools, public_queues, public_status, stage_upload, submit_request
from apps.machines.public_printer_service_serializers import PublicPrinterPoolSerializer, PublicPrinterQueueSerializer, PublicPrinterStatusSerializer, PublicPrinterSubmitResponseSerializer, PublicPrinterSubmitSerializer, PublicPrinterUploadSerializer
from apps.makerspaces.lookup import get_public_makerspace
from apps.makerspaces.platform import module_enabled
from apps.machines.public_intake_access import require_job_requests
from apps.machines.views_public_service import require_public_machine_requester
from apps.machines.views_public_service_status import STATUS_ERRORS
from apps.machines.permissions import IsActiveRequester


def _require_printer_module(makerspace):
    """The public printer surface belongs to `machine_service`.

    The 3D print queue was a separate `printing` module until decision 340b folded it into
    machine service, which takes requests for every machine type. An edition that hides
    `machine_service` makes every one of these routes answer 404 first.
    """
    from apps.makerspaces.editions import require_public_surface

    require_public_surface("machine_service")
    if not module_enabled(makerspace, "machine_service"):
        from apps.makerspaces.guards import module_off
        raise module_off("machine_service")


class PublicPrinterQueuesView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ClientTierRateThrottle]
    throttle_scope = "public_read"

    @extend_schema(tags=["Public machine service"], auth=[], responses={200: PublicPrinterQueueSerializer(many=True)})
    def get(self, request, makerspace_slug):
        makerspace = get_public_makerspace(makerspace_slug)
        _require_printer_module(makerspace)
        require_job_requests(makerspace)  # discovery follows the intake switch (dec 221e)
        return Response(PublicPrinterQueueSerializer(public_queues(makerspace), many=True).data)


class PublicPrinterPoolsView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ClientTierRateThrottle]
    throttle_scope = "public_read"

    @extend_schema(tags=["Public machine service"], auth=[], responses={200: PublicPrinterPoolSerializer(many=True)})
    def get(self, request, makerspace_slug):
        makerspace = get_public_makerspace(makerspace_slug)
        _require_printer_module(makerspace)
        require_job_requests(makerspace)  # discovery follows the intake switch (dec 221e)
        return Response(PublicPrinterPoolSerializer(public_pools(makerspace), many=True).data)


class PublicPrinterUploadView(APIView):
    permission_classes = [IsActiveRequester]
    throttle_classes = [ClientTierRateThrottle]
    throttle_scope = "print_request_submit"

    @extend_schema(tags=["Public machine service"], request=PublicPrinterUploadSerializer,
                   responses={201: PublicPrinterSubmitResponseSerializer, 403: OpenApiResponse(ErrorSerializer),
                              404: OpenApiResponse(ErrorSerializer, description="Public machine intake unavailable or module off.")})
    def post(self, request, makerspace_slug):
        makerspace = get_public_makerspace(makerspace_slug)
        _require_printer_module(makerspace)
        require_public_machine_requester(request.user, makerspace)
        serializer = PublicPrinterUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(stage_upload(makerspace, serializer.validated_data, request.user), status=status.HTTP_201_CREATED)


class PublicPrinterRequestView(APIView):
    permission_classes = [IsActiveRequester]
    throttle_classes = [ClientTierRateThrottle]
    throttle_scope = "print_request_submit"

    @extend_schema(tags=["Public machine service"], request=PublicPrinterSubmitSerializer,
                   responses={201: PublicPrinterSubmitResponseSerializer, 403: OpenApiResponse(ErrorSerializer),
                              404: OpenApiResponse(ErrorSerializer, description="Public machine intake unavailable or module off.")})
    def post(self, request, makerspace_slug):
        makerspace = get_public_makerspace(makerspace_slug)
        _require_printer_module(makerspace)
        if str(request.data.get("website", "")).strip():
            decoy = SimpleNamespace(public_token=uuid.uuid4(), status=MachineServiceRequest.Status.PENDING)
            return Response(PublicPrinterSubmitResponseSerializer(decoy).data, status=status.HTTP_201_CREATED)
        require_public_machine_requester(request.user, makerspace)
        serializer = PublicPrinterSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = submit_request(makerspace, serializer.validated_data, request.user)
        return Response(PublicPrinterSubmitResponseSerializer(row).data, status=status.HTTP_201_CREATED)


class PublicPrinterStatusView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ClientTierRateThrottle]
    throttle_scope = "request_status"

    @extend_schema(tags=["Public machine service"], auth=[], responses={200: PublicPrinterStatusSerializer, **STATUS_ERRORS},
                   description="PII-free printer job status plus the shared derived `eta` (null once terminal).")
    def get(self, request, public_token):
        row, context = public_status(public_token)
        return Response(PublicPrinterStatusSerializer(row, context=context).data)
