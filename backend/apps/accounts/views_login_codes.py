"""Resend the emailed code of an unusual sign-in (lane S-B)."""

from collections.abc import Mapping

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from apps.accounts import login_code_flow
from apps.accounts.audit_events import fingerprint
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.openapi_errors import errors


class LoginCodeResendThrottle(SimpleRateThrottle):
    """Per challenge: on top of the hard cap of two resends."""
    scope = "login_code_resend"

    def get_cache_key(self, request, view):
        value = str(request.data.get("challenge") or "")[:200] if isinstance(request.data, Mapping) else ""
        return self.cache_format % {"scope": self.scope, "ident": fingerprint(value)}


class LoginCodeIPThrottle(SimpleRateThrottle):
    scope = "login_code_ip"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class LoginCodeResendSerializer(serializers.Serializer):
    challenge = serializers.CharField(min_length=20, max_length=200, write_only=True)


class LoginCodeResentSerializer(serializers.Serializer):
    sent = serializers.BooleanField()
    expires_in = serializers.IntegerField(help_text="Seconds the new code stays valid.")
    resends_left = serializers.IntegerField()


class LoginCodeResendView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    login_ip_guard = True  # S-C: IP rules, automatic blocks, Turnstile (CAPTCHA action ``code``)
    throttle_classes = [LoginCodeIPThrottle, LoginCodeResendThrottle]

    @extend_schema(
        tags=["MFA"], auth=[], request=LoginCodeResendSerializer,
        summary="Email a new code for an unusual sign-in",
        description=(
            "For a challenge with `purpose: risk` (factor `email_code`). The new code replaces the old one "
            "and lasts 10 minutes; a challenge allows two resends. `login_code_invalid` (400) when the "
            "challenge is not a live risk challenge or has no resends left."),
        responses={200: LoginCodeResentSerializer,
                   400: OpenApiResponse(ErrorSerializer, description="`login_code_invalid`."),
                   **errors(429)},
    )
    def post(self, request):
        serializer = LoginCodeResendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        response = Response(login_code_flow.resend(serializer.validated_data["challenge"], request))
        response["Cache-Control"] = "no-store"
        return response
