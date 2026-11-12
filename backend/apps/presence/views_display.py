"""Public presence-now additions and the token-addressed screen protocol (decision 307)."""
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from apps.makerspaces.lookup import get_public_makerspace
from apps.makerspaces.platform import module_enabled
from . import display_pairing
from .display_state import state_for
from .here_now import here_now
from .policy import require_enabled
from .public_feed import machines_now
from .schema import ERRORS
from .serializers_display import (
    DisplayRegisterResponseSerializer, DisplayStateSerializer, HereNowSerializer, MachinesNowSerializer,
)
from .views_public import PresenceTVThrottle, PresenceTVUserThrottle, check_origin


class DisplayRegisterThrottle(AnonRateThrottle):
    scope = "presence_display_register"
    rate = "30/hour"


class DisplayPollThrottle(AnonRateThrottle):
    scope = "presence_display_poll"
    rate = "30/minute"


class PresenceHereNowView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [PresenceTVThrottle, PresenceTVUserThrottle]

    @extend_schema(tags=["Presence"], auth=[], responses={200: HereNowSerializer, **ERRORS},
                   description="Who is here now, as person cards. A logged-out visitor sees only people whose "
                               "profile is open to the web and who did not hide their presence; a signed-in user "
                               "sees every visible profile except those who hid presence. Everyone else is only "
                               "in `others_count`. Guests, minors and members without a profile are counted.")
    def get(self, request, makerspace_slug):
        space = get_public_makerspace(makerspace_slug)
        require_enabled(space)
        check_origin(request, space)
        from .display_config import apply_privacy
        from .views_now_config import read
        response = Response(apply_privacy(here_now(space, request.user, request), read(space)["privacy"]))
        response["Cache-Control"] = "private, no-store"  # the body depends on who is asking
        response["Vary"] = "Origin, Authorization"
        return response


class PublicMachinesNowView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [PresenceTVThrottle, PresenceTVUserThrottle]

    @extend_schema(tags=["Presence"], auth=[], responses={200: MachinesNowSerializer, **ERRORS},
                   description="Public machines only: in use, free or out of service. Never who is using one.")
    def get(self, request, makerspace_slug):
        space = get_public_makerspace(makerspace_slug)
        if not module_enabled(space, "machines"):
            raise NotFound()
        check_origin(request, space)
        return Response(machines_now(space))


class DisplayRegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [DisplayRegisterThrottle]

    @extend_schema(tags=["Space displays"], auth=[], request=None,
                   responses={201: DisplayRegisterResponseSerializer, 429: OpenApiResponse(description="Rate limited.")},
                   description="A screen asks for a pairing code and a secret. Staff claim the code in the console. "
                               "One network (an IPv4 address or an IPv6 /64) may hold only a few waiting screens.")
    def post(self, request):
        row, secret = display_pairing.register(client_ip=DisplayRegisterThrottle().get_ident(request))
        response = Response({"token": secret, "code": row.pairing_code,
                             "code_expires_at": row.code_expires_at.isoformat()}, status=201)
        response["Cache-Control"] = "no-store"
        return response


SCHEME = "display "


def header_token(request):
    """The secret from `Authorization: Display <secret>`, else None (it never travels in a URL path)."""
    value = request.META.get("HTTP_AUTHORIZATION", "")
    if value[:len(SCHEME)].lower() != SCHEME:
        return None
    return value[len(SCHEME):].strip() or None


def state_response(token):
    if not token:
        raise NotFound()
    row = display_pairing.resolve(token)
    if row.makerspace_id is None and row.code_expires_at < timezone.now():
        raise NotFound()
    response = Response(state_for(row))
    response["Cache-Control"] = "no-store"
    response["Vary"] = "Authorization"
    return response


STATE_DESCRIPTION = ("The screen polls this with its secret. An unknown, revoked or switched-off screen gets the "
                     "same 404; the screen then registers again. The paired body is the logged-out public view "
                     "and nothing private.")


class DisplayStateHeaderView(APIView):
    """Decision 335(d): the secret rides in a header on a fixed path, so no access log ever records it."""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [DisplayPollThrottle]

    @extend_schema(tags=["Space displays"], auth=[], responses={200: DisplayStateSerializer, **ERRORS},
                   description=STATE_DESCRIPTION + " Send the secret as `Authorization: Display <secret>`; a "
                                                   "missing or other scheme is the same 404.")
    def get(self, request):
        return state_response(header_token(request))


class DisplayStateView(APIView):
    """Deprecated path form, kept for screens still running an older page; its secret is redacted from logs."""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [DisplayPollThrottle]

    @extend_schema(tags=["Space displays"], auth=[], deprecated=True, responses={200: DisplayStateSerializer, **ERRORS},
                   description=STATE_DESCRIPTION + " Deprecated: use `GET /space-displays/state/` with "
                                                   "`Authorization: Display <secret>`.")
    def get(self, request, token):
        return state_response(token)
