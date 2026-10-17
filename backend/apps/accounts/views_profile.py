"""Browser login, refresh, logout, and current-user endpoints."""

from django.conf import settings
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from apps.accounts import audit_events
from apps.accounts.auth_cookies import (
    assert_csrf,
    clear_refresh_cookies,
    set_refresh_cookies,
)
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
from apps.accounts.models import User


from .views_refresh import _assert_staff_refresh_scope, _refresh_surface
from .session_context import SessionContextSerializer, cookie_name, decode_cookie, request_context

class LogoutView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Auth"],
        summary="Log out and clear refresh cookie",
        auth=[],
        request=SessionContextSerializer,
        responses={
            204: OpenApiResponse(description="Logged out of the selected account context."),
            401: OpenApiResponse(description="Refresh token could not be blacklisted."),
            403: OpenApiResponse(description="CSRF check failed."),
        },
    )
    def post(self, request, *args, **kwargs):
        context = request_context(request)
        cookie = request.COOKIES.get(cookie_name(context))
        assert_csrf(request, surface=_refresh_surface(cookie) if cookie else None)
        actor = None
        if cookie:
            try:
                token = decode_cookie(cookie, context)
            except TokenError as exc:
                raise InvalidToken("Invalid refresh cookie.") from exc
            actor = User.objects.filter(pk=token.get("user_id"), account_kind=token.get("kind")).first()
            if actor is not None:
                from apps.accounts.surface_policy import validate_account_token, assert_surface
                validate_account_token(actor, token)
                assert_surface(actor, token.get("surface"), request)
            _assert_staff_refresh_scope(request, cookie)
        if cookie:
            try:
                # A claim refresh will not decode as a plain RefreshToken, and logout
                # must still revoke it.
                try:
                    refresh = ClaimRefreshToken(cookie)
                except TokenError:
                    refresh = SpaceWorksRefreshToken(cookie)
                refresh.blacklist()
                if actor is not None and refresh.get("sid"):
                    from apps.accounts.web_sessions import revoke_session
                    revoke_session(actor, refresh["sid"])
            except TokenError:
                pass
        audit_events.record_auth_event(
            actor,
            "auth.logout",
            target=actor,
            meta={"had_refresh_cookie": bool(cookie)},
        )
        response = Response(status=204)
        clear_refresh_cookies(response, context=context)
        return response


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Auth"],
        summary="Get current staff profile",
        request=None,
        responses={
            200: UserPayloadSerializer,
            400: OpenApiResponse(description="Invalid request."),
            401: OpenApiResponse(description="Authentication credentials were not provided."),
            403: OpenApiResponse(description="Permission denied."),
            429: OpenApiResponse(description="Request throttled."),
        },
    )
    def get(self, request, *args, **kwargs):
        return Response(user_payload(request.user, request=request))
