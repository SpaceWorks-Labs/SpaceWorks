"""GitHub browser OAuth: a provider-verified member session, or for a person MFA is
mandatory for (staff) the MFA challenge, finished at ``auth/mfa/verify`` (#62)."""

from django.db import IntegrityError
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts import audit_events, device_memory
from apps.accounts.login_risk import record_success
from apps.accounts.auth_cookies import set_refresh_cookies
from apps.accounts.github_browser import (
    GithubRejected, GithubUnavailable, github_settings, start_github_attempt,
)
from apps.accounts.github_http import github_claims
from apps.accounts.login_methods import self_registration_enabled
from apps.accounts.oidc_browser_attempts import OidcAttemptRejected, consume_attempt
from apps.accounts.serializers import user_payload
from apps.accounts.serializers_github import (
    GithubBrowserStartResponseSerializer, GithubBrowserStartSerializer,
)
from apps.accounts.serializers_oidc_browser import (
    OidcBrowserCallbackSerializer, OidcBrowserLoginResponseSerializer,
)
from apps.accounts.services_social_identity import SocialResolutionError, resolve_social_identity
from apps.accounts.services_social_login import issue_social_session, social_audit_meta, staff_challenge
from apps.accounts.serializers_mfa import MFAChallengeResponseSerializer
from drf_spectacular.utils import PolymorphicProxySerializer
from apps.accounts.views_social_helpers import _error
from apps.makerspaces.import_adoption import adopt_pending_memberships_for_user
from apps.openapi_errors import errors


def _failure(reason, request=None):
    audit_events.record_auth_event(
        None, "auth.social_login_failed", meta={"provider": "github", "reason": reason}
    )
    if request is not None:  # S-B: feeds the failure counters
        from apps.accounts.security_signals import send_login_refused
        send_login_refused(request, "", f"social_{reason}")


class GithubBrowserStartView(APIView):
    permission_classes = [AllowAny]
    login_ip_guard = True  # S-C: platform IP rules, automatic blocks, Turnstile
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "social_nonce"

    @extend_schema(
        tags=["Social auth"], auth=[], request=GithubBrowserStartSerializer,
        responses={200: GithubBrowserStartResponseSerializer, **errors(400, 403, 429, 503)},
    )
    def post(self, request):
        serializer = GithubBrowserStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            row = github_settings()
            started = start_github_attempt(request, row, **serializer.validated_data)
        except GithubUnavailable:
            _failure("provider_unavailable")
            return _error("social_unavailable", 503)
        except (OidcAttemptRejected, IntegrityError):
            _failure("attempt_rejected")
            return _error("social_invalid", 403)
        return Response(started)


class GithubBrowserCallbackView(APIView):
    permission_classes = [AllowAny]
    login_ip_guard = True  # S-C: platform IP rules, automatic blocks, Turnstile
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "social_login"

    @extend_schema(
        tags=["Social auth"], auth=[], request=OidcBrowserCallbackSerializer,
        responses={200: PolymorphicProxySerializer(
            component_name="GithubBrowserLoginResult",
            serializers=[OidcBrowserLoginResponseSerializer, MFAChallengeResponseSerializer], resource_type_field_name=None),
            **errors(400, 401, 403, 409, 429, 503)},
    )
    def post(self, request):
        serializer = OidcBrowserCallbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            attempt = consume_attempt(
                request, state=data["state"], nonce=data["nonce"], provider="github"
            )
            row = github_settings()
            claims = github_claims(row, attempt, data["code"])
            user, outcome = resolve_social_identity(
                provider="github", claims=claims, surface="member",
                allow_user_creation=self_registration_enabled(),
            )
            # Same as the Google/Apple path: a verified email recovers imported memberships.
            adopt_pending_memberships_for_user(user)
            challenge = staff_challenge(request, user, delivery="web")
            if challenge is None:
                tokens = issue_social_session(user, surface="member", delivery="web", nonce_row=attempt)
        except (OidcAttemptRejected, GithubRejected):
            _failure("invalid_token_or_attempt", request)
            return _error("social_invalid", 401)
        except GithubUnavailable:
            _failure("provider_unavailable")
            return _error("social_unavailable", 503)
        except SocialResolutionError as exc:
            _failure(exc.code, request)
            return _error(exc.code, exc.status_code)
        audit_events.record_auth_event(
            user, "auth.social_login_succeeded", target=user,
            meta=social_audit_meta("github", outcome, claims["sub"]),
        )
        if challenge is not None:
            response = Response(challenge)
            response["Cache-Control"] = "no-store"
            return response
        record_success(request, user, method="social", web=True)  # Q4: recorded, never stepped up
        response = Response({"access": tokens["access"],
                             "user": user_payload(user, request=request, session_authority="member"),
                             "outcome": outcome})
        set_refresh_cookies(response, tokens["refresh"], request)
        device_memory.attach(response, request)
        return response
