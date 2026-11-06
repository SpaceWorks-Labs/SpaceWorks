"""Browser login, refresh, logout, and current-user endpoints."""

from django.utils.translation import gettext
from django.conf import settings
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.exceptions import APIException, AuthenticationFailed
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.accounts import audit_events
from apps.accounts.auth_cookies import (
    assert_csrf,
    clear_refresh_cookies,
    csrf_surface,
    set_refresh_cookies,
)
from apps.accounts.models import User
from apps.accounts.claim_sessions import ClaimSessionInvalid
from apps.accounts.claim_tokens import ClaimRefreshToken, rotate_claim_refresh
from apps.accounts.schemas_auth import (
    LoginRequestSerializer,
    LoginResponseSerializer,
    LogoutResponseSerializer,
    RefreshResponseSerializer,
    UserPayloadSerializer,
)
from apps.accounts.serializers import LoginSerializer, SpaceWorksTokenRefreshSerializer, user_payload
from apps.accounts.tokens import SpaceWorksRefreshToken
from apps.accounts.session_context import SessionContextSerializer, cookie_name, decode_cookie, request_context


def _refresh_user_is_active(token_str):
    """Return False if the refresh token's user is suspended/restricted/inactive."""
    try:
        token = SpaceWorksRefreshToken(token_str)
    except TokenError:
        return True
    user = User.objects.filter(pk=token.get("user_id")).first()
    return bool(
        user
        and not user.is_tenant_dump_stub
        and user.is_active
        and user.access_status == User.AccessStatus.ACTIVE
    )


class RefreshView(TokenRefreshView):
    serializer_class = SpaceWorksTokenRefreshSerializer
    @extend_schema(
        tags=["Auth"],
        summary="Refresh access token",
        auth=[],
        request=SessionContextSerializer,
        responses={
            200: RefreshResponseSerializer,
            401: OpenApiResponse(description="Missing, invalid, or replayed refresh token."),
            403: OpenApiResponse(description="CSRF check failed or account restricted."),
        },
    )
    def post(self, request, *args, **kwargs):
        context = request_context(request)
        cookie = request.COOKIES.get(cookie_name(context))
        try:
            assert_csrf(request, surface=csrf_surface(context))
            if cookie:
                token = decode_cookie(cookie, context)
                if token.get("kind") == "platform":
                    from apps.accounts.surface_policy import assert_surface
                    actor = User.objects.filter(pk=token.get("user_id")).first()
                    if actor is None:
                        raise AuthenticationFailed(gettext("Account is not available."))
                    assert_surface(actor, token.get("surface"), request)
        except TokenError as exc:
            audit_events.record_refresh_rejected(cookie, "invalid_token")
            raise InvalidToken("Invalid refresh cookie.") from exc
        except APIException:
            audit_events.record_auth_event(
                None, "auth.refresh_rejected", meta={"reason": "csrf"}
            )
            raise
        if not cookie:
            audit_events.record_auth_event(
                None, "auth.refresh_rejected", meta={"reason": "missing_cookie"}
            )
            raise InvalidToken("No refresh cookie.")
        # A claim refresh rotates through its own path: the deadline lives on the claim
        # row and is re-read there, which is why rotation cannot extend it.
        try:
            ClaimRefreshToken(cookie)
        except TokenError:
            is_claim_refresh = False
        else:
            is_claim_refresh = True
        if is_claim_refresh:
            try:
                pair, actor = rotate_claim_refresh(cookie)
            except (TokenError, ClaimSessionInvalid) as exc:
                actor = audit_events.user_from_refresh_token(cookie)
                audit_events.record_auth_event(
                    actor,
                    "auth.refresh_rejected",
                    target=actor,
                    meta={"reason": "invalid_claim_session"},
                )
                raise InvalidToken("Claim session is no longer active.") from exc
            audit_events.record_auth_event(
                actor, "auth.refresh_succeeded", target=actor
            )
            response = Response({"access": pair.access, "user": user_payload(actor, request=request)})
            set_refresh_cookies(response, pair.refresh, request, context=context)
            return response
        if not _refresh_user_is_active(cookie):
            actor = audit_events.user_from_refresh_token(cookie)
            audit_events.record_auth_event(
                actor,
                "auth.refresh_rejected",
                target=actor,
                meta={"reason": "restricted_account"},
            )
            response = Response({"detail": gettext("Account access is restricted.")}, status=403)
            clear_refresh_cookies(response, context=context)
            return response
        serializer = self.get_serializer(data={"refresh": cookie}, context={"request": request, "session_context": context})
        try:
            serializer.is_valid(raise_exception=True)
        except InvalidToken:
            # InvalidToken subclasses AuthenticationFailed, so it must be caught first
            # or the device-refresh arm below would swallow every malformed token.
            audit_events.record_refresh_rejected(cookie, "invalid_token")
            raise
        except AuthenticationFailed as exc:
            audit_events.record_refresh_rejected(
                cookie,
                "device_refresh_wrong_endpoint"
                if exc.get_codes() == "device_refresh_wrong_endpoint"
                else "invalid_token",
            )
            raise
        except TokenError as exc:
            audit_events.record_refresh_rejected(cookie, "invalid_token")
            raise InvalidToken(str(exc)) from exc
        data = serializer.validated_data
        actor = audit_events.user_from_refresh_token(data.get("refresh"))
        audit_events.record_auth_event(actor, "auth.refresh_succeeded", target=actor)
        response = Response({"access": data["access"], "user": data["user"]})
        new_refresh = data.get("refresh")
        if new_refresh:
            set_refresh_cookies(response, new_refresh, request, context=context)
        return response


