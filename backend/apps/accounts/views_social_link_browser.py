"""Browser link flow for GitHub and configured OIDC providers (signed-in members only)."""

from django.db import IntegrityError
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts import audit_events
from apps.accounts.github_browser import GithubRejected, GithubUnavailable
from apps.accounts.models_social import SocialIdentity
from apps.accounts.oidc_browser_attempts import OidcAttemptRejected
from apps.accounts.oidc_browser_http import OidcProviderUnavailable, OidcTokenRejected
from apps.accounts.serializers_github import GithubBrowserStartResponseSerializer, GithubBrowserStartSerializer
from apps.accounts.serializers_oidc_browser import (
    OidcBrowserCallbackSerializer, OidcBrowserStartResponseSerializer, SocialLinkStartSerializer,
)
from apps.accounts.serializers_social import SocialIdentitySerializer
from apps.accounts.services_social_identity import SocialResolutionError
from apps.accounts.social_jwt import SocialProviderUnavailable, SocialTokenError
from apps.accounts.social_link_browser import finish_link, start_github_link, start_oidc_link
from apps.accounts.views_social_helpers import _error
from apps.audit import services as audit
from apps.openapi_errors import errors

START = ("Start linking a provider to the signed-in member's browser session. The returned state is "
         "bound to this session and nonce, and can only be finished by POST /auth/social/link/callback "
         "from the same session; it never signs anyone in. Staff, platform and device sessions are refused.")


def _started(call):
    try:
        return Response(call())
    except SocialResolutionError as exc:
        return _error(exc.code, exc.status_code)
    except (GithubUnavailable, OidcProviderUnavailable):
        return _error("social_unavailable", 503)
    except (OidcAttemptRejected, IntegrityError):
        return _error("social_invalid", 403)


class GithubLinkStartView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "social_nonce"

    @extend_schema(tags=["Social auth"], request=GithubBrowserStartSerializer, description=START,
                   responses={200: GithubBrowserStartResponseSerializer, **errors(400, 401, 403, 429, 503)})
    def post(self, request):
        serializer = GithubBrowserStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Linking binds to the signed-in session and never carries a post-login `next` path.
        data = {key: value for key, value in serializer.validated_data.items() if key != "next"}
        return _started(lambda: start_github_link(request, **data))


class OidcLinkStartView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "social_nonce"

    @extend_schema(tags=["Social auth"], request=SocialLinkStartSerializer, description=START,
                   responses={200: OidcBrowserStartResponseSerializer, **errors(400, 401, 403, 404, 429, 503)})
    def post(self, request, slug):
        serializer = SocialLinkStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return _started(lambda: start_oidc_link(request, slug, **serializer.validated_data))


class SocialLinkCallbackView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "social_login"

    @extend_schema(tags=["Social auth"], request=OidcBrowserCallbackSerializer, description=(
        "Finish a link started by social/github/link/authorize or social/oidc/{slug}/link/authorize. "
        "409 identity_conflict when that provider identity belongs to another account; 409 "
        "provider_already_linked when a different identity from the provider is already linked."),
        responses={200: SocialIdentitySerializer, **errors(400, 401, 403, 409, 429, 503)})
    def post(self, request):
        serializer = OidcBrowserCallbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            provider, claims = finish_link(request, **serializer.validated_data)
        except (OidcAttemptRejected, GithubRejected, OidcTokenRejected, SocialTokenError):
            return _error("social_invalid", 401)
        except (GithubUnavailable, OidcProviderUnavailable, SocialProviderUnavailable):
            return _error("social_unavailable", 503)
        except SocialResolutionError as exc:
            if getattr(exc, "provider", ""):
                # Same literal metadata as the ID-token link route's refusal.
                audit_events.record_auth_event(request.user, "auth.social_identity_link_failed", target=request.user,
                                               meta={"provider": exc.provider, "reason": exc.code})
            return _error(exc.code, exc.status_code)
        identity = SocialIdentity.objects.get(user=request.user, provider=provider)
        audit.record(request.user, "auth.social_identity_linked", target=request.user,
                     meta={"provider": provider, "subject_hash": audit_events.fingerprint(claims["sub"])})
        return Response(SocialIdentitySerializer(identity).data)
