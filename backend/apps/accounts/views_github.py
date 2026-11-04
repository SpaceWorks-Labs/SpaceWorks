"""GitHub browser OAuth, always delivering a provider-verified member session."""

from django.db import IntegrityError
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts import audit_events
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
from apps.accounts.services_social_login import issue_social_session, social_audit_meta
from apps.accounts.views_social_helpers import _error
from apps.makerspaces.import_adoption import adopt_pending_memberships_for_user
from apps.openapi_errors import errors


def _failure(reason):
    audit_events.record_auth_event(
        None, "auth.social_login_failed", meta={"provider": "github", "reason": reason}
    )


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
        responses={200: OidcBrowserLoginResponseSerializer,
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
            tokens = issue_social_session(user, surface="member", delivery="web", nonce_row=attempt)
        except (OidcAttemptRejected, GithubRejected):
            _failure("invalid_token_or_attempt")
            return _error("social_invalid", 401)
        except GithubUnavailable:
            _failure("provider_unavailable")
            return _error("social_unavailable", 503)
        except SocialResolutionError as exc:
            _failure(exc.code)
            return _error(exc.code, exc.status_code)
        audit_events.record_auth_event(
            user, "auth.social_login_succeeded", target=user,
            meta=social_audit_meta("github", outcome, claims["sub"]),
        )
        response = Response({"access": tokens["access"],
                             "user": user_payload(user, request=request, session_authority="member"),
                             "outcome": outcome})
        set_refresh_cookies(response, tokens["refresh"], request)
        return response
