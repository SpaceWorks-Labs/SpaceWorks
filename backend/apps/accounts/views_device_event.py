"""The native event-role step-up (#173): a person's device session asks for an event grant.

A person who holds an active event role (judge, mentor, volunteer or crew lead: a live event staff
grant for that event) and no other way into its desks natively names the event, re-attests the app
and proves their second factor, exactly as for the staff step-up. The MFA challenge returned here
finishes through the ordinary ``auth/mfa/verify`` route and yields a NEW grant with authority
``event`` limited to that event's programme routes. It carries no staff authority, never reaches a
staff route, and is revoked when the role ends; the member grant it started from keeps working.
"""

from django.utils.translation import gettext
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
from apps.accounts.serializers_device import DeviceEventGrantSerializer
from apps.accounts.serializers_mfa import MFAChallengeResponseSerializer
from apps.accounts.services_device_tokens import assert_mobile_grant_creation_enabled
from apps.accounts.services_event_grants import ACTIVE, event_role_state, live_event
from apps.accounts.views_device import IsDeviceAccessToken, _reject_browser_headers
from apps.hardware_requests.exceptions import ErrorSerializer

STEP_UP_DESCRIPTION = " ".join(__doc__.split(chr(10) + chr(10), 1)[1].split())


class EventRoleRequired(PermissionDenied):
    default_code = "event_role_required"

    def __init__(self):
        super().__init__({"detail": "You do not hold an active role in that event.", "code": self.default_code})


class DeviceEventGrantView(APIView):
    permission_classes = [IsAuthenticated, IsDeviceAccessToken]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "device_attestation_challenge"

    @extend_schema(
        tags=["Device auth"], request=DeviceEventGrantSerializer,
        summary="Step a device session up to an event-role grant limited to one event",
        description=STEP_UP_DESCRIPTION + " " + ATTESTATION_DESCRIPTION,
        responses={
            200: MFAChallengeResponseSerializer,
            400: OpenApiResponse(ErrorSerializer),
            401: OpenApiResponse(ErrorSerializer, description="Invalid attestation or device session."),
            403: OpenApiResponse(ErrorSerializer, description="event_role_required, or a browser transport."),
            426: OpenApiResponse(ErrorSerializer, description="native_app_update_required"),
            503: OpenApiResponse(ErrorSerializer, description="attestation_unavailable"),
        },
    )
    def post(self, request):
        _reject_browser_headers(request)
        serializer = DeviceEventGrantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data, grant, user = serializer.validated_data, request.device_grant, request.user
        assert_supported(grant.platform, data.get("app_version"))
        event = live_event(data["event_id"])
        if event is None or event_role_state(user, event.pk) != ACTIVE:
            raise EventRoleRequired()
        assert_mobile_grant_creation_enabled()
        challenge = consume_attestation_challenge(
            data["challenge"], platform=grant.platform, app_id=grant.app_id, environment=grant.environment)
        if challenge is None:
            raise AuthenticationFailed(gettext("Invalid device attestation."))
        try:
            verified = verify_attestation(challenge, data["challenge"], data["attestation"])
        except AttestationUnavailable:
            return Response({"detail": gettext("Device attestation is unavailable."), "code": "attestation_unavailable"},
                            status=503)
        except AttestationRejected as exc:
            raise AuthenticationFailed(gettext("Invalid device attestation.")) from exc
        if challenge.registration.makerspace_id not in (None, event.makerspace_id):
            raise AuthenticationFailed(gettext("Device registration is not approved for that event."))
        from apps.accounts.mfa_challenges import start
        from apps.accounts.mfa_sessions import context, device_context
        device = device_context(challenge, verified, login_method=grant.login_method)
        device["event_id"] = event.pk
        with transaction.atomic():
            result = start(user, context=context(request, surface="member", device=device))
        response = Response(result)
        response["Cache-Control"] = "no-store"
        return response
