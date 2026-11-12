"""Native GitHub sign-in (decision 358 A): start, then the device-delivery code exchange.

Mirrors `views_social_login.SocialLoginView` with ``delivery=device``: same switches, same
account linking (`resolve_social_identity`), same MFA challenge for a person MFA is mandatory
for, same device grant issuance and the same audit events (provider ``github``).
"""

from django.db import IntegrityError
from drf_spectacular.utils import OpenApiResponse, PolymorphicProxySerializer, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts import audit_events
from apps.accounts.attestation import AttestationRejected, AttestationUnavailable
from apps.accounts.github_browser import GithubRejected, GithubUnavailable, github_settings
from apps.accounts.github_http import github_claims
from apps.accounts.github_native import consume_native_github, start_native_github
from apps.accounts.login_methods import self_registration_enabled
from apps.accounts.login_risk import record_success
from apps.accounts.serializers_device import DeviceGrantSerializer
from apps.accounts.serializers_github_native import (
    GithubNativeExchangeSerializer, GithubNativeStartResponseSerializer, GithubNativeStartSerializer,
)
from apps.accounts.serializers_mfa import MFAChallengeResponseSerializer
from apps.accounts.serializers_payload import user_payload
from apps.accounts.serializers_social import SocialLoginResponseSerializer
from apps.accounts.services_phone_device import NATIVE_PLATFORM
from apps.accounts.services_social_identity import SocialResolutionError, resolve_social_identity
from apps.accounts.services_social_login import (
    SocialDeviceGrantRetryRequired, issue_social_session, social_audit_meta, staff_challenge,
)
from apps.accounts.social_nonces import SocialDeviceRestartRequired, SocialNonceRejected, verify_nonce_attestation
from apps.accounts.views_device import _reject_browser_headers
from apps.accounts.views_social_helpers import _audit_failure, _challenged, _error
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.import_adoption import adopt_pending_memberships_for_user
from apps.openapi_errors import errors

PROVIDER = "github"
RESULT = PolymorphicProxySerializer(
    component_name="GithubNativeLoginResult", serializers=[SocialLoginResponseSerializer, MFAChallengeResponseSerializer],
    resource_type_field_name=None)


class GithubNativeStartView(APIView):
    permission_classes = [AllowAny]
    login_ip_guard = True  # S-C: platform IP rules, automatic blocks, Turnstile
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "social_nonce"

    @extend_schema(
        tags=["Social auth"], auth=[], request=GithubNativeStartSerializer,
        summary="Start native GitHub sign-in (PKCE, app-link redirect)",
        description="Returns the GitHub authorize URL with a one-time `state` bound to this device (its grant, "
                    "or for a first grant the unspent attestation challenge) and to the app's S256 "
                    "`code_challenge`. GitHub redirects to `redirect_uri`, an HTTPS app link on the deployment's "
                    "primary web host. Refused 404 social_unavailable when GitHub sign-in is off or unconfigured.",
        responses={200: GithubNativeStartResponseSerializer, **errors(400, 403, 404, 429)},
    )
    def post(self, request):
        _reject_browser_headers(request)
        serializer = GithubNativeStartSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            started = start_native_github(request, client_platform=data["client_platform"],
                                          code_challenge=data["code_challenge"], challenge=data.get("challenge"))
        except GithubUnavailable:
            _audit_failure(PROVIDER, "provider_unavailable")
            return _error("social_unavailable", 404)
        except (SocialNonceRejected, IntegrityError):
            _audit_failure(PROVIDER, "attempt_rejected", request)
            return _error("social_invalid", 403)
        # The web flow's event name: it describes the shared attempt ledger; provider and delivery tell them apart.
        audit_events.record_auth_event(None, "auth.oidc_browser_attempt_started",
                                       meta={"provider": PROVIDER, "delivery": "device", "transition": False})
        response = Response(started)
        response["Cache-Control"] = "no-store"
        return response


class GithubNativeLoginView(APIView):
    permission_classes = [AllowAny]
    login_ip_guard = True  # S-C: platform IP rules, automatic blocks, Turnstile
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "social_login"

    @extend_schema(
        tags=["Social auth"], auth=[], request=GithubNativeExchangeSerializer,
        summary="Finish native GitHub sign-in (code + verifier exchange, device delivery)",
        description="Post the `code` and `state` GitHub put on the app link with the PKCE `code_verifier`. The "
                    "state is single use and bound to the device and the verifier: a replayed state, another "
                    "device's state or a wrong verifier is refused (401 social_invalid, or 409 "
                    "social_device_restart_required once a first-grant attestation challenge is burned). Same "
                    "switches, account linking and staff MFA challenge as the web GitHub flow; 426 "
                    "native_app_update_required for an app older than the platform minimum.",
        responses={200: RESULT, **errors(400, 401, 403, 404, 429, 503),
                   409: OpenApiResponse(ErrorSerializer, description="social_device_restart_required"),
                   426: OpenApiResponse(ErrorSerializer, description="native_app_update_required")},
    )
    def post(self, request):
        _reject_browser_headers(request)
        serializer = GithubNativeExchangeSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        from apps.accounts.native_app_version import assert_supported
        assert_supported(NATIVE_PLATFORM.get(data["client_platform"]), data.get("app_version"))
        try:
            row = github_settings()  # the switches answer before the one-time state is spent
        except GithubUnavailable:
            return _error("social_unavailable", 404)
        nonce_row = None
        try:
            nonce_row, attestation_challenge, attempt = consume_native_github(
                request, state=data["state"], code_verifier=data["code_verifier"],
                client_platform=data["client_platform"], challenge=data.get("challenge"))
            verified = None
            if attestation_challenge is not None:
                verified = verify_nonce_attestation(nonce_row, attestation_challenge, data["challenge"],
                                                    data["attestation"])
            claims = github_claims(row, attempt, data["code"])
            user, outcome = resolve_social_identity(provider=PROVIDER, claims=claims, surface="member",
                                                    allow_user_creation=self_registration_enabled())
            if nonce_row.device_grant_id is not None and nonce_row.device_grant.user_id != user.pk:
                raise SocialResolutionError("access_denied", 403)
            adopt_pending_memberships_for_user(user)
            challenge = staff_challenge(request, user, delivery="device", nonce_row=nonce_row,
                                        verified_attestation=verified)
            if challenge is not None:
                return _challenged(PROVIDER, user, outcome, claims, {"delivery": "device"}, challenge)
            tokens = issue_social_session(user, surface="member", delivery="device", nonce_row=nonce_row,
                                          verified_attestation=verified)
            request.device_grant = tokens["device_grant"]
        except SocialDeviceRestartRequired:
            _audit_failure(PROVIDER, "device_restart_required", request)
            return _error("social_device_restart_required", 409)
        except (SocialNonceRejected, GithubRejected):
            _audit_failure(PROVIDER, "invalid_token_or_attempt", request)
            if nonce_row is not None and nonce_row.attestation_challenge_id:
                return _error("social_device_restart_required", 409)
            return _error("social_invalid", 401)
        except AttestationUnavailable:
            _audit_failure(PROVIDER, "attestation_unavailable")
            return _error("attestation_unavailable", 503)
        except AttestationRejected:
            _audit_failure(PROVIDER, "attestation_failed", request)
            return _error("social_device_restart_required", 409)
        except GithubUnavailable:
            _audit_failure(PROVIDER, "provider_unavailable")
            if nonce_row is not None and nonce_row.attestation_challenge_id:
                return _error("social_device_restart_required", 409)
            return _error("social_unavailable", 503)
        except SocialDeviceGrantRetryRequired:
            _audit_failure(PROVIDER, "device_grant_failed")
            return _error("social_device_restart_required", 409)
        except SocialResolutionError as exc:
            _audit_failure(PROVIDER, exc.code, request)
            return _error(exc.code, exc.status_code)
        audit_events.record_auth_event(user, "auth.social_login_succeeded", target=user,
                                       meta=social_audit_meta(PROVIDER, outcome, claims["sub"]))
        trust = record_success(request, user, method="social", web=False)
        from apps.accounts.native_event_grants import session_authority_for
        grant = tokens["device_grant"]
        response = Response({
            "access": tokens["access"], "refresh": tokens["refresh"],
            "user": user_payload(user, request=request, session_authority=session_authority_for(grant)),
            "outcome": outcome, "device_grant": DeviceGrantSerializer(grant).data, "device_trust": trust,
        })
        response["Cache-Control"] = "no-store"
        return response
