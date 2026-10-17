"""Browser login, refresh, logout, and current-user endpoints."""

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.exceptions import APIException
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError

from apps.accounts import audit_events
from apps.accounts.auth_cookies import (
    assert_csrf,
    clear_refresh_cookies,
)
from apps.accounts.schemas_auth import UserPayloadSerializer
from apps.accounts.serializers import user_payload
from apps.accounts.services_browser_logout import revoke_browser_cookie
from .session_context import SessionContextSerializer, cookie_name, request_context


class LogoutView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Auth"],
        summary="Log out and clear refresh cookie",
        auth=[],
        request=SessionContextSerializer,
        responses={
            204: OpenApiResponse(description="Logged out of the selected account context."),
            401: OpenApiResponse(description="Invalid account context; selected cookie cleared."),
            403: OpenApiResponse(description="CSRF check failed."),
        },
    )
    def post(self, request, *args, **kwargs):
        context = request_context(request)
        cookie = request.COOKIES.get(cookie_name(context))
        # An expired/blacklisted cookie cannot tell us which origin policy to
        # use. The explicit namespace keeps that policy stable after revocation.
        assert_csrf(request, surface="member" if context == "member" else "staff")
        actor = None
        response = Response(status=204)
        if cookie:
            try:
                actor = revoke_browser_cookie(cookie, context, request)
            except TokenError:
                # Logout is idempotent even after reset/revocation/expiry.
                pass
            except APIException as exc:
                # Preserve context/scope refusals without trapping the stale
                # cookie in the browser or consuming a different context's token.
                response = self.handle_exception(exc)
        audit_events.record_auth_event(
            actor,
            "auth.logout",
            target=actor,
            meta={"had_refresh_cookie": bool(cookie)},
        )
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
