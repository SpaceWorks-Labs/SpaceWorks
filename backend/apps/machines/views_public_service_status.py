"""Anonymous bearer-token status page data for every machine-service job type."""

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.apiclients.throttling import ClientTierRateThrottle
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.machines.public_service_serializers import PublicMachineServiceStatusSerializer
from apps.machines.public_service_status import public_service_status

STATUS_ERRORS = {
    400: OpenApiResponse(ErrorSerializer, description="The job's makerspace has machine service (or printing) disabled."),
    404: OpenApiResponse(description="Unknown, unservable or edition-hidden tracking token."),
    429: OpenApiResponse(ErrorSerializer, description="Status lookup rate limit exceeded."),
}


class PublicMachineServiceStatusView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ClientTierRateThrottle]
    throttle_scope = "request_status"

    @extend_schema(
        tags=["Public machine service"], auth=[],
        summary="Read a machine-service job's status and estimated start/finish by tracking token",
        description=("PII-free allowlist plus a derived `eta` (null for terminal jobs). The token is a "
                     "read capability only and never authorizes a write."),
        responses={200: PublicMachineServiceStatusSerializer, **STATUS_ERRORS},
    )
    def get(self, request, public_token):
        row, context = public_service_status(public_token)
        return Response(PublicMachineServiceStatusSerializer(row, context=context).data)
