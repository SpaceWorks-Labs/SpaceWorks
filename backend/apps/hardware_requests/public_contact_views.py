"""Send the one-time email code an account-less borrow request needs (owner decision #80)."""

from django.http import Http404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.hardware_requests.contact_verification import issue_code
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.hardware_requests.serializers import ContactCodeRequestSerializer
from apps.hardware_requests.throttles import (
    AnonymousRequestEmailThrottle,
    AnonymousRequestIpBurstThrottle,
    AnonymousRequestIpHourThrottle,
)
from apps.makerspaces.guards import require_feature
from apps.makerspaces.lookup import get_public_makerspace
from apps.makerspaces.request_access import contact_requests_allowed
from apps.openapi import PUBLIC_API_AUTH_PARAMETERS


class RequestContactCodeView(APIView):
    """Mail a 6-digit code to the borrower's address, for spaces without member accounts.

    Always answers 202 with no delivery detail, so the endpoint cannot be used to learn
    whether an address exists anywhere. A space with member accounts answers 404: its
    borrowers sign in instead.
    """

    permission_classes = [AllowAny]
    throttle_classes = [AnonymousRequestIpBurstThrottle, AnonymousRequestIpHourThrottle]

    @extend_schema(
        tags=["Public requests"],
        summary="Send a borrow-request email code",
        auth=[{"jwtAuth": []}, {}],
        parameters=PUBLIC_API_AUTH_PARAMETERS,
        request=ContactCodeRequestSerializer,
        responses={
            202: OpenApiResponse(description="Code sent if delivery is possible; expires in 10 minutes."),
            400: OpenApiResponse(ErrorSerializer, description="Invalid email or loans disabled."),
            404: OpenApiResponse(description="Makerspace not found, or it uses member accounts."),
            429: OpenApiResponse(description="Too many codes for this address or client."),
        },
    )
    def post(self, request, makerspace_slug, *args, **kwargs):
        makerspace = get_public_makerspace(makerspace_slug)
        if not contact_requests_allowed(makerspace):
            raise Http404()
        require_feature(makerspace, "loans.enabled")
        serializer = ContactCodeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if str(serializer.validated_data.get("website", "")).strip():
            return Response(status=status.HTTP_202_ACCEPTED)  # honeypot: decoy, no send
        request.anonymous_contact_email = serializer.validated_data["email"]
        throttle = AnonymousRequestEmailThrottle()
        if not throttle.allow_request(request, self):
            self.throttled(request, throttle.wait())
        issue_code(makerspace, serializer.validated_data["email"])
        return Response(status=status.HTTP_202_ACCEPTED)
