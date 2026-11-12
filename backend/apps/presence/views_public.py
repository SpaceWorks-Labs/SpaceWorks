from django.utils.translation import gettext
from urllib.parse import urlsplit

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.makerspaces.lookup import get_public_makerspace
from apps.makerspaces.platform import makerspace_public_origins
from .display import tv_payload
from .policy import PresenceError, require_enabled
from .serializers import PresenceTVRowSerializer
from .schema import ERRORS


def check_origin(request, space):
    raw = request.headers.get("Origin") or request.headers.get("Referer")
    if raw:
        try:
            parts = urlsplit(raw)
            origin = f"{parts.scheme}://{parts.netloc}"
        except ValueError:
            origin = ""
        if origin not in makerspace_public_origins(space):
            raise PresenceError("origin_denied", gettext("This origin cannot view this makerspace."), status_code=403)
    # Also bind custom request hosts, independent of the browser Origin header.
    from apps.makerspaces.models import Makerspace
    from apps.makerspaces.hosting import canonical_host
    host = canonical_host(request.get_host())
    tenants = Makerspace.objects.filter(frontend_domain__iexact=host) if host else Makerspace.objects.none()
    if tenants.exists() and not tenants.filter(pk=space.pk, frontend_domain_status="verified").exists():
        raise PresenceError("origin_denied", gettext("This host cannot view this makerspace."), status_code=403)


class PresenceTVThrottle(AnonRateThrottle):
    scope = "presence_tv"
    rate = "120/minute"


class PresenceTVUserThrottle(UserRateThrottle):
    scope = "presence_tv_user"
    rate = "120/minute"


class PresenceNowView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [PresenceTVThrottle, PresenceTVUserThrottle]

    @extend_schema(tags=["Presence"], auth=[], responses={200: PresenceTVRowSerializer(many=True), **ERRORS},
                   description="Anonymous current presence projection; tenant/origin/module gates apply. No history or identifiers.")
    def get(self, request, makerspace_slug):
        space = get_public_makerspace(makerspace_slug)
        require_enabled(space)
        check_origin(request, space)
        preview = request.user.is_authenticated and rbac.can(request.user, rbac.Action.MANAGE_MEMBERS, space.pk)
        response = Response(tv_payload(space, use_cache=not preview))
        # Shared server cache is tenant-only. Browser/shared intermediary caching is
        # bounded, and authenticated previews never enter intermediary caches.
        response["Cache-Control"] = "no-store" if preview else "public, max-age=0, s-maxage=0"
        response["Vary"] = "Origin"
        return response
