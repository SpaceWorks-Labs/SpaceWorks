"""Authenticated social identity listing, linking and unlinking."""

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import audit_events
from apps.accounts.reauthentication import require_recent_reauth
from apps.accounts.models_oidc import slug_from_provider_key
from apps.accounts.models_social import SocialIdentity, SocialProvider
from apps.accounts.throttles import NativeSocialLinkThrottle
from apps.accounts.serializers_social import SocialIdentitySerializer, SocialLinkSerializer
from apps.accounts.services_social_identity import (
    SocialResolutionError, resolve_social_identity, unlink_social_identity,
)
from apps.accounts.social_jwt import SocialProviderUnavailable, SocialTokenError
from apps.accounts.social_nonces import (
    SocialAuthUnavailable, SocialDeviceRestartRequired, SocialNonceRejected, consume_social_nonce,
    native_apple_audience,
    provider_settings,
)
from apps.accounts.views_social_helpers import _error
from apps.audit import services as audit
from apps.openapi_errors import errors
from apps.accounts.staff_identity import is_person


LINK_DESCRIPTION = (
    "Link a provider to the signed-in member. Browser sessions send client_platform web with a "
    "web nonce. Device sessions send android or ios with a nonce from POST /auth/social/nonce "
    "(delivery device, no challenge), which binds it to the current device grant; they also need "
    "recent reauthentication (403 recent_reauth_required) and are throttled. Staff accounts are refused."
)


class SocialProviderListLinkView(APIView):
    permission_classes = [IsAuthenticated]
    # Only native linking spends the budget (the throttle skips every other request); a
    # throttle class rather than a get_throttles() override keeps the pre-auth guard exact.
    throttle_classes = [NativeSocialLinkThrottle]
    throttle_scope = "social_link"

    @extend_schema(tags=["Social auth"], responses={200: SocialIdentitySerializer(many=True), **errors(401, 403)})
    def get(self, request):
        rows = SocialIdentity.objects.filter(user=request.user).order_by("provider")
        return Response(SocialIdentitySerializer(rows, many=True).data)

    @extend_schema(tags=["Social auth"], request=SocialLinkSerializer, description=LINK_DESCRIPTION,
        responses={200: SocialIdentitySerializer, **errors(400, 401, 403, 404, 409, 429, 503)})
    def post(self, request):
        if not is_person(request.user):
            return _error("social_invalid", 403)
        serializer = SocialLinkSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        grant = getattr(request, "device_grant", None)
        if grant is not None:
            # Checked before the nonce is consumed, so a refusal does not burn it.
            require_recent_reauth(request)
        try:
            _settings, audience = provider_settings(data["provider"], data["client_platform"])
            if grant is not None and data["provider"] == SocialProvider.APPLE:
                audience = native_apple_audience(_settings, grant)
            consume_social_nonce(request, raw=data["nonce"], provider=data["provider"],
                surface="member", delivery="device" if grant else "web",
                client_platform=data["client_platform"], provider_audience=audience)
            from apps.accounts.views_social import _verify
            claims = _verify(data["provider"], data["id_token"], data["nonce"], audience)
            resolve_social_identity(provider=data["provider"], claims=claims, surface="member",
                apple_name=data.get("apple_name", ""), explicit_user=request.user)
        except SocialAuthUnavailable:
            return _error("social_unavailable", 404)
        except (SocialNonceRejected, SocialDeviceRestartRequired, SocialTokenError) as exc:
            if grant is not None:
                audit_events.record_auth_event(
                    request.user, "auth.social_identity_link_failed", target=request.user,
                    meta={"provider": data["provider"], "reason": type(exc).__name__, "delivery": "device"})
            return _error("social_invalid", 401)
        except SocialProviderUnavailable:
            return _error("social_unavailable", 503)
        except SocialResolutionError as exc:
            # Same reasoning as the login view: the nonce was consumed before
            # `_explicit_link` could refuse a walk-in record, so the refusal is recorded
            # against a real actor rather than left as a silent 403.
            audit_events.record_auth_event(
                request.user, "auth.social_identity_link_failed", target=request.user,
                meta={"provider": data["provider"], "reason": exc.code},
            )
            return _error(exc.code, exc.status_code)
        identity = SocialIdentity.objects.get(user=request.user, provider=data["provider"])
        subject_hash = audit_events.fingerprint(claims["sub"])
        # Literal metadata per branch keeps the reviewed audit catalogue exact.
        if grant is None:
            audit.record(request.user, "auth.social_identity_linked", target=request.user,
                         meta={"provider": data["provider"], "subject_hash": subject_hash})
        else:
            audit.record(request.user, "auth.social_identity_linked", target=request.user,
                         meta={"provider": data["provider"], "subject_hash": subject_hash,
                               "delivery": "device", "grant_hash": audit_events.fingerprint(grant.pk)})
        return Response(SocialIdentitySerializer(identity).data)


class SocialProviderDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Social auth"], request=None, responses={204: None, **errors(401, 403, 404, 409)})
    def delete(self, request, provider):
        if provider not in SocialProvider.values and not slug_from_provider_key(provider):
            return _error("identity_not_found", 404)
        try:
            unlink_social_identity(request.user, provider)
        except SocialResolutionError as exc:
            return _error(exc.code, exc.status_code)
        audit.record(request.user, "auth.social_identity_unlinked", target=request.user, meta={"provider": provider})
        return Response(status=status.HTTP_204_NO_CONTENT)


