"""Native passkey sign-in endpoints (358 B): ``auth/device/passkey/options`` and ``/login``.

Errors: ``passkey_failed`` (400), ``passkeys_unavailable`` (403), ``rp_id_unavailable`` (400),
an untyped 401 for an invalid or spent attestation challenge (the device-login answer),
``attestation_unavailable`` (503), ``native_app_update_required`` (426), 429.
"""

import json

from django.utils.translation import gettext
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts import audit_events
from apps.accounts.attestation import AttestationRejected, AttestationUnavailable, verify_attestation
from apps.accounts.native_app_version import assert_supported
from apps.accounts.passkeys.native_login import (
    NativePasskeyRetryRequired, begin_native_login, finish_native_login,
)
from apps.accounts.passkeys.serializers import PasskeyOptionsSerializer
from apps.accounts.serializers_attestation import ATTESTATION_DESCRIPTION, AttestationPayloadField
from apps.accounts.serializers_device import (
    APP_VERSION_HELP, DeviceGrantSerializer, DeviceIdentitySerializer, DeviceTokenResponseSerializer,
)
from apps.accounts.serializers_payload import user_payload
from apps.accounts.services_device_grants import DeviceSuperadminNotSupported, audit_grant_refusal
from apps.accounts.throttles import DeviceLoginThrottle
from apps.accounts.views_device import _consume_challenge, _reject_browser_headers
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.openapi_errors import errors


class DevicePasskeyOptionsSerializer(DeviceIdentitySerializer):
    challenge = serializers.CharField(max_length=512, trim_whitespace=False,
                                      help_text="An unspent attestation challenge; not consumed here.")


class DevicePasskeyLoginSerializer(DevicePasskeyOptionsSerializer):
    ceremony = serializers.UUIDField(help_text="From auth/device/passkey/options; valid once, for 5 minutes.")
    credential = serializers.JSONField(help_text="The platform authenticator's assertion (PublicKeyCredential JSON, "
                                                 "base64url binary fields).")
    attestation = AttestationPayloadField()
    app_version = serializers.CharField(max_length=32, required=False, help_text=APP_VERSION_HELP)

    def validate_attestation(self, value):
        if not isinstance(value, dict) or not value or len(value) > 16:
            raise serializers.ValidationError(gettext("Invalid attestation payload."))
        return value


def _audit_failure(data, reason):
    audit_events.record_auth_event(None, "auth.device_login_failed", meta={
        "reason": reason, "method": "passkey", "platform": data.get("platform"),
        "app_hash": audit_events.fingerprint(data.get("app_id"))})


class DevicePasskeyOptionsView(APIView):
    permission_classes = [AllowAny]
    login_ip_guard = True  # S-C: platform IP rules, automatic blocks, Turnstile
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "passkey_options"

    @extend_schema(
        tags=["Device auth"], auth=[], request=DevicePasskeyOptionsSerializer,
        summary="Start a native passkey sign-in",
        description="WebAuthn request options for a discoverable passkey. The RP ID is the deployment's public web "
                    "domain (PUBLIC_APP_BASE_URL, the domain apple-app-site-association `webcredentials` and "
                    "assetlinks `get_login_creds` bind the app to); the expected origin is derived from the attested "
                    "app (iOS `https://<rp id>`, Android `android:apk-key-hash:<cert digest>`), never from a header.",
        responses={200: PasskeyOptionsSerializer, **errors(400, 401, 403, 429)},
    )
    def post(self, request):
        _reject_browser_headers(request)
        serializer = DevicePasskeyOptionsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ceremony, options_json = begin_native_login(**serializer.validated_data)
        response = Response({"ceremony": str(ceremony.pk), "options": json.loads(options_json)})
        response["Cache-Control"] = "no-store"
        return response


class DevicePasskeyLoginView(APIView):
    permission_classes = [AllowAny]
    login_ip_guard = True  # S-C: platform IP rules, automatic blocks, Turnstile
    throttle_classes = [DeviceLoginThrottle]

    @extend_schema(
        tags=["Device auth"], auth=[], request=DevicePasskeyLoginSerializer,
        summary="Finish a native passkey sign-in (attested member grant)",
        description="Consumes the attestation challenge and the ceremony, verifies the assertion and issues a member "
                    "device grant whose session is MFA-verified by the passkey (`mfa_method=passkey`). Same platform "
                    "and per-space passkey switches as the web sign-in. " + ATTESTATION_DESCRIPTION,
        responses={200: DeviceTokenResponseSerializer, **errors(400, 401, 403, 429),
                   426: OpenApiResponse(ErrorSerializer, description="native_app_update_required"),
                   503: OpenApiResponse(ErrorSerializer, description="attestation_unavailable")},
    )
    def post(self, request):
        _reject_browser_headers(request)
        serializer = DevicePasskeyLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        assert_supported(data["platform"], data.get("app_version"))
        challenge = _consume_challenge(data)
        if challenge is None:
            _audit_failure(data, "invalid_challenge")
            raise AuthenticationFailed(gettext("Invalid device credentials or attestation."))
        try:
            verified = verify_attestation(challenge, data["challenge"], data["attestation"])
        except AttestationUnavailable:
            _audit_failure(data, "provider_unavailable")
            return Response({"detail": gettext("Device attestation is unavailable."),
                             "code": "attestation_unavailable"}, status=503)
        except AttestationRejected as exc:
            _audit_failure(data, "attestation_rejected")
            raise AuthenticationFailed(gettext("Invalid device credentials or attestation.")) from exc
        try:
            user, access, refresh, grant = finish_native_login(
                request, ceremony_id=data["ceremony"], credential=data["credential"],
                challenge=challenge, verified=verified)
        except NativePasskeyRetryRequired as exc:
            _audit_failure(data, "registration_not_approved")
            raise AuthenticationFailed(gettext("Invalid device credentials or attestation.")) from exc
        except DeviceSuperadminNotSupported as exc:
            audit_grant_refusal(exc)
            raise
        from apps.accounts.login_risk import record_success
        response = Response({"access": access, "refresh": refresh,
                             "user": user_payload(user, request=request, session_authority="member"),
                             "device_grant": DeviceGrantSerializer(grant).data,
                             "device_trust": record_success(request, user, method="passkey", web=False)})
        response["Cache-Control"] = "no-store"
        return response
