"""A non-rotating, cookie-presence-only gate for anonymous browser telemetry."""
from urllib.parse import urlsplit

from django.conf import settings
from django.utils.cache import patch_vary_headers
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from apps.openapi_errors import errors
from .auth_cookies import _origin_allowed
from .session_context import LEGACY_STAFF_COOKIE_PREFIX, PERSON, PLATFORM, cookie_name
from django.utils.translation import gettext


class BrowserStateSerializer(serializers.Serializer):
    state = serializers.ChoiceField(choices=("anonymous", "auth_present", "unknown"))


class BrowserStateThrottle(AnonRateThrottle):
    scope = "browser-state"
    rate = "120/hour"


def _origin_context(request):
    origin = request.headers.get("Origin")
    raw = origin or request.headers.get("Referer", "")
    try:
        parts = urlsplit(raw)
        if (parts.scheme not in ("http", "https") or not parts.netloc or parts.username or parts.password
                or (origin and (parts.path or parts.query or parts.fragment))):
            return False, False
        candidate = f"{parts.scheme}://{parts.netloc}"
        same_origin = f"{request.scheme}://{request.get_host()}"
        allowed = candidate == same_origin or _origin_allowed(candidate, surface="member")
        # Browser metadata refers to the visible URL, even if an internal proxy
        # rewrites Host. A direct cross-origin call must remain unknown.
        same_browser_origin = allowed and request.headers.get("Sec-Fetch-Site") == "same-origin"
        return allowed, same_browser_origin
    except ValueError:
        return False, False


class BrowserStateView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [BrowserStateThrottle]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        patch_vary_headers(response, ("Cookie", "Authorization", "Origin", "Referer", "Sec-Fetch-Site"))
        return response

    @extend_schema(tags=["Authentication"], summary="Check whether browser credentials are present",
                   description="Presence only; never validates or rotates a session. Unknown/error must disable tracking.",
                   responses={200: BrowserStateSerializer, **errors(403, 429)})
    def get(self, request):
        allowed, same_origin = _origin_context(request)
        if not allowed:
            raise PermissionDenied(gettext("Origin not allowed."))
        names = request.COOKIES
        present = ("Authorization" in request.headers or cookie_name(PERSON) in names
                   or cookie_name(PLATFORM) in names or settings.SESSION_COOKIE_NAME in names
                   or any(name.startswith(LEGACY_STAFF_COOKIE_PREFIX) for name in names))
        return Response({"state": "auth_present" if present else ("anonymous" if same_origin else "unknown")})
