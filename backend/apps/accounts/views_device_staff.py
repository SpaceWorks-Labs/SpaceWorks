"""The native staff step-up (Q12): a person's device session asks for a staff grant.

A staff grant is a step-up on a person, never a separate account: an active device
session of the person (from ANY primary login method -- password, social or phone) names
one makerspace where they hold a staff role, re-attests the app, and proves their second
factor. The MFA challenge this returns finishes through the ordinary ``auth/mfa/verify``
(or enrolment) routes and yields a NEW grant with authority ``staff`` fixed to that
makerspace; the member grant it started from keeps working.
"""

from django.db import transaction
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.attestation import (
    AttestationRejected, AttestationUnavailable, consume_attestation_challenge, verify_attestation,
)
from apps.accounts.native_app_version import assert_supported
from apps.accounts.serializers_attestation import ATTESTATION_DESCRIPTION
from apps.accounts.serializers_device import DeviceStaffGrantSerializer
from apps.accounts.serializers_mfa import MFAChallengeResponseSerializer
from apps.accounts.services_device_login import staff_makerspace_for
from apps.accounts.services_device_tokens import assert_mobile_grant_creation_enabled
from apps.accounts.staff_identity import has_staff_role
from apps.accounts.views_device import IsDeviceAccessToken, _reject_browser_headers
from apps.hardware_requests.exceptions import ErrorSerializer


STEP_UP_DESCRIPTION = " ".join(__doc__.split(chr(10) + chr(10), 1)[1].split())


class StaffAccessRequired(PermissionDenied):
    default_code = "staff_access_required"

    def __init__(self):
        super().__init__({"detail": "You do not hold a staff role in that makerspace.", "code": self.default_code})


class DeviceStaffGrantView(APIView):
    permission_classes = [IsAuthenticated, IsDeviceAccessToken]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "device_attestation_challenge"

    @extend_schema(
        tags=["Device auth"], request=DeviceStaffGrantSerializer,
        summary="Step a device session up to a staff grant fixed to one makerspace",
        description=STEP_UP_DESCRIPTION + " " + ATTESTATION_DESCRIPTION,
        responses={
            200: MFAChallengeResponseSerializer,
            400: OpenApiResponse(ErrorSerializer),
            401: OpenApiResponse(ErrorSerializer, description="Invalid attestation or device session."),
            403: OpenApiResponse(ErrorSerializer, description="staff_access_required, or a browser transport."),
            426: OpenApiResponse(ErrorSerializer, description="native_app_update_required"),
            503: OpenApiResponse(ErrorSerializer, description="attestation_unavailable"),
        },
    )
    def post(self, request):
        _reject_browser_headers(request)
        serializer = DeviceStaffGrantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data, grant, user = serializer.validated_data, request.device_grant, request.user
        assert_supported(grant.platform, data.get("app_version"))
        space = staff_makerspace_for(data["makerspace"])
        if space is None or not has_staff_role(user, space):
            raise StaffAccessRequired()
        assert_mobile_grant_creation_enabled()
        challenge = consume_attestation_challenge(
            data["challenge"], platform=grant.platform, app_id=grant.app_id, environment=grant.environment)
        if challenge is None:
            raise AuthenticationFailed("Invalid device attestation.")
        try:
            verified = verify_attestation(challenge, data["challenge"], data["attestation"])
        except AttestationUnavailable:
            return Response({"detail": "Device attestation is unavailable.", "code": "attestation_unavailable"},
                            status=503)
        except AttestationRejected as exc:
            raise AuthenticationFailed("Invalid device attestation.") from exc
        if challenge.registration.makerspace_id not in (None, space):
            raise AuthenticationFailed("Device registration is not approved for that makerspace.")
        from apps.accounts.mfa_challenges import start
        from apps.accounts.mfa_sessions import context, device_context
        device = device_context(challenge, verified, login_method=grant.login_method)
        device["staff_makerspace_id"] = space
        with transaction.atomic():
            result = start(user, context=context(request, surface="member", device=device))
        response = Response(result)
        response["Cache-Control"] = "no-store"
        return response
