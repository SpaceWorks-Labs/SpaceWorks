"""Staff console API for Displays: list, claim a code, change panels and rotation, unpair."""
from datetime import timedelta

from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from . import display_pairing
from .anthias_sync import display_url
from .models_display import DisplayScreen
from .schema import ERRORS
from .serializers_display import (
    DisplayAdminSerializer, DisplayClaimSerializer, DisplayConfigSerializer, DisplayListSerializer,
)
from .views_staff import StaffPresenceView, staff_space

ONLINE_WITHIN = timedelta(seconds=60)


class DisplayClaimThrottle(UserRateThrottle):
    """L-D2: a person may try only so many pairing codes; the space's own failure budget is in `claim`."""
    scope = "presence_display_claim"
    rate = "30/hour"


def _row(screen, now, *, url=""):
    """One screen for the console. `url` (the secret-bearing address) is passed only by provision and rotate (L-D3)."""
    return {"id": screen.pk, "name": screen.name, "panels": screen.panels, "rotation_seconds": screen.rotation_seconds,
            "announcement": screen.announcement, "layout": screen.layout, "theme": screen.theme,
            "privacy": screen.privacy, "refresh_seconds": screen.refresh_seconds,
            "slide_seconds": screen.slide_seconds or {}, "player_ids": [p.pk for p in screen.players.all()],
            "has_link": bool(screen.link_secret_enc), "url": url, "claimed_at": screen.claimed_at, "last_seen_at": screen.last_seen_at,
            "online": bool(screen.last_seen_at and now - screen.last_seen_at <= ONLINE_WITHIN)}


class DisplayListClaimView(StaffPresenceView):
    def get_throttles(self):
        extra = [DisplayClaimThrottle()] if self.request.method == "POST" else []
        return [*super().get_throttles(), *extra]

    @extend_schema(tags=["Space displays"], responses={200: DisplayListSerializer, **ERRORS},
                   description="Requires manage_makerspace. `enabled` is the presence.public_display switch.")
    def get(self, request, makerspace_id):
        space = staff_space(request, makerspace_id, settings=True)
        now = timezone.now()
        rows = (DisplayScreen.objects.filter(makerspace=space, revoked_at__isnull=True)
                .select_related("makerspace").prefetch_related("players").order_by("name", "pk"))
        return Response({"enabled": display_pairing.display_enabled(space),
                         "displays": [_row(r, now) for r in rows]})

    @extend_schema(tags=["Space displays"], request=DisplayClaimSerializer, responses={201: DisplayAdminSerializer, **ERRORS},
                   description="Claim the code a screen shows. 404 if the code is unknown or expired; 409 "
                               "`paired_displays_quota_reached` at the space's limit; 429 after too many wrong "
                               "codes (per person, and `display_claim_throttled` per space).")
    def post(self, request, makerspace_id):
        space = staff_space(request, makerspace_id, settings=True)
        serializer = DisplayClaimSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        row = display_pairing.claim(request.user, space, data.pop("code"), data)
        return Response(_row(row, timezone.now()), status=201)


class DisplayDetailView(StaffPresenceView):
    @extend_schema(tags=["Space displays"], request=DisplayConfigSerializer, responses={200: DisplayAdminSerializer, **ERRORS})
    def patch(self, request, makerspace_id, pk):
        space = staff_space(request, makerspace_id, settings=True)
        serializer = DisplayConfigSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = display_pairing.update(request.user, space, pk, dict(serializer.validated_data))
        return Response(_row(row, timezone.now()))

    @extend_schema(tags=["Space displays"], request=None, responses={204: None, **ERRORS},
                   description="Unpair: the screen's secret stops working immediately.")
    def delete(self, request, makerspace_id, pk):
        space = staff_space(request, makerspace_id, settings=True)
        display_pairing.unpair(request.user, space, pk)
        return Response(status=204)


class DisplayProvisionView(StaffPresenceView):
    @extend_schema(tags=["Space displays"], request=DisplayConfigSerializer, responses={201: DisplayAdminSerializer, **ERRORS},
                   description="Create a screen that needs no pairing code: its address (`url`) carries the secret in "
                               "the fragment. For players that cannot type a code, such as Anthias. The address is "
                               "returned here and by New address only; lists never show it again.")
    def post(self, request, makerspace_id):
        space = staff_space(request, makerspace_id, settings=True)
        serializer = DisplayConfigSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row, _secret = display_pairing.provision(request.user, space, dict(serializer.validated_data))
        return Response(_row(row, timezone.now(), url=display_url(row)), status=201)


class DisplayRotateLinkView(StaffPresenceView):
    @extend_schema(tags=["Space displays"], request=None, responses={200: DisplayAdminSerializer, **ERRORS},
                   description="Issue a new address for a screen; the old one stops working at once. The new "
                               "address is in `url` of this response only.")
    def post(self, request, makerspace_id, pk):
        space = staff_space(request, makerspace_id, settings=True)
        row, _secret = display_pairing.rotate_link(request.user, space, pk)
        from .anthias_sync import schedule_sync
        schedule_sync(row)  # players hold the old address until the next sync
        return Response(_row(row, timezone.now(), url=display_url(row)))
