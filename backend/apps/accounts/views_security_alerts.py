"""'This wasn't me' (lane S-B). Token-only: no cookie or bearer is read, so the route is
CSRF-exempt by construction and a signed-in browser adds no authority to it."""

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts import security_not_me
from apps.accounts.auth_cookies import clear_refresh_cookies
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.openapi_errors import errors


class NotMeRequestSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=512, write_only=True,
                                  help_text="The value after `#token=` in the alert link.")


class MfaResetContactSerializer(serializers.Serializer):
    name = serializers.CharField()
    slug = serializers.CharField()


class MfaResetContactsSerializer(serializers.Serializer):
    superadmin = serializers.BooleanField(help_text="The platform administrator can always reset two-step sign-in.")
    space_managers_of = MfaResetContactSerializer(
        many=True, help_text="Spaces whose Space Manager may reset it for this person (the MFA-reset rule).")


class NotMeResultSerializer(serializers.Serializer):
    signed_out = serializers.BooleanField()
    password_reset_requested = serializers.BooleanField(
        help_text="A reset code was requested for the account email (sent unless recovery mail is off).")
    mfa_reset = MfaResetContactsSerializer()


class SecurityAlertNotMeView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "security_alert_action"

    @extend_schema(
        tags=["Auth"], auth=[], request=NotMeRequestSerializer,
        summary="Report a security alert as not you",
        description=(
            "Signs the account out everywhere, forgets every remembered device, turns the password off "
            "and requests a reset code to the account email. Second factors are kept. The link works once; "
            "using any alert, or completing a password reset, expires every other alert. Refusals are "
            "`security_alert_used` (400)."),
        responses={200: NotMeResultSerializer,
                   400: OpenApiResponse(ErrorSerializer, description="`security_alert_used`."),
                   **errors(429)},
    )
    def post(self, request):
        serializer = NotMeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        response = Response(security_not_me.use(serializer.validated_data["token"], request))
        # The browser that opened the link may hold this account's session: end it here too.
        clear_refresh_cookies(response, request=request)
        response["Cache-Control"] = "no-store"
        return response
