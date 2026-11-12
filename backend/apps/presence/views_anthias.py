"""Staff API for a space's Anthias players (decision 325c). Needs manage_makerspace and display.anthias_push."""
import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from apps.audit import services as audit
from apps.outbound_throttles import ANTHIAS_PLAYER_THROTTLES
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.guards import feature_off
from apps.tenant_migration.gate_runtime import tenant_write
from . import anthias_sync
from .anthias_client import AnthiasError, clean_host
from .display_pairing import display_enabled, set_players
from .models_anthias import AnthiasPlayer
from .policy import PresenceError, require_staff
from .schema import ERRORS as PRESENCE_ERRORS
from .serializers_anthias import (
    AnthiasPlayerListSerializer, AnthiasPlayerSerializer, AnthiasPlayerWriteSerializer, AnthiasTestSerializer,
    DisplayPlayersSerializer,
)
from .serializers_display import DisplayAdminSerializer
from .views_display_admin import _row
from .views_staff import StaffPresenceView, staff_space

logger = logging.getLogger(__name__)
MAX_PLAYERS = 10
FEATURE = "display.anthias_push"
# Decision 329 (d): a switched-off route answers the typed 404 like every other gate.
ERRORS = {**PRESENCE_ERRORS, 404: OpenApiResponse(ErrorSerializer, description=(
    "Makerspace, player or presence unavailable; or the switch is off: typed `feature_disabled` with "
    "`feature` = `display.anthias_push` (player routes) or `presence.public_display` (screen players)."))}


# Decision 336(g): what the player answered (timeout, refused, 404, 302, bad JSON ...) is not told to the
# caller, or Test would be a port and service scanner for anything the server can reach. Only reasons decided
# BEFORE any connection (the address itself) stay distinct; the fine reason goes to the server log only.
PRE_CONNECT_REASONS = frozenset({"invalid_host", "dns_failed", "blocked_address", "private_address", "no_link"})


def coarse_reason(reason):
    if not reason:
        return ""
    return reason if reason in PRE_CONNECT_REASONS else "failed"


def _player_row(player):
    return {"id": player.pk, "name": player.name, "host_url": player.host_url, "username": player.username,
            "has_password": bool(player.password_enc), "api_version": player.api_version,
            "anthias_version": player.anthias_version, "status": player.status,
            "last_error": coarse_reason(player.last_error), "last_synced_at": player.last_synced_at}


def _space(request, makerspace_id):
    space = staff_space(request, makerspace_id, settings=True)
    if not anthias_sync.anthias_enabled(space):
        raise feature_off(FEATURE)
    return space


def _player(space, pk):
    player = AnthiasPlayer.objects.select_related("makerspace").filter(pk=pk, makerspace=space).first()
    if player is None:
        raise NotFound()
    return player


def _apply(player, data):
    if "name" in data:
        player.name = data["name"].strip()
    if "host_url" in data:
        try:
            host = clean_host(data["host_url"])
        except AnthiasError:
            raise PresenceError("invalid_host", gettext("Use http:// or https:// and a host, for example http://192.168.1.20.")) from None
        if player.pk and host != player.host_url and "password" not in data:
            # Decision 336(g): the stored password belongs to the old host. Repointing the player elsewhere and
            # pressing Test would otherwise send it to whatever now answers there.
            player.set_password("")
        player.host_url = host
        player.api_version = player.anthias_version = ""
    if "username" in data:
        player.username = data["username"].strip()
    if "password" in data:
        player.set_password(data["password"])


class AnthiasPlayersView(StaffPresenceView):
    @extend_schema(tags=["Space displays"], responses={200: AnthiasPlayerListSerializer, **ERRORS},
                   description="Players registered for this space. Passwords are never returned (`has_password` only).")
    def get(self, request, makerspace_id):
        space = staff_space(request, makerspace_id, settings=True)
        enabled = anthias_sync.anthias_enabled(space)
        rows = AnthiasPlayer.objects.filter(makerspace=space).order_by("name", "pk") if enabled else []
        return Response({"enabled": enabled, "allow_private_hosts": bool(settings.ANTHIAS_ALLOW_PRIVATE_HOSTS),
                         "players": [_player_row(p) for p in rows]})

    @extend_schema(tags=["Space displays"], request=AnthiasPlayerWriteSerializer, responses={201: AnthiasPlayerSerializer, **ERRORS})
    def post(self, request, makerspace_id):
        space = _space(request, makerspace_id)
        serializer = AnthiasPlayerWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if not data.get("name") or not data.get("host_url"):
            raise PresenceError("missing_fields", gettext("A name and a host are required."))
        with tenant_write(space.pk):
            require_staff(request.user, space, settings=True)
            from apps.managed_hosting.extra_quotas import check_extra_quota
            check_extra_quota(space, "anthias_players")  # decision 328a: refuses only a NEW player
            if AnthiasPlayer.objects.filter(makerspace=space).count() >= MAX_PLAYERS:
                raise PresenceError("anthias_players_limit", gettext("A space can register up to 10 players."), status_code=409)
            player = AnthiasPlayer(makerspace=space)
            _apply(player, data)
            player.save()
            audit.record(request.user, "presence.anthias_player_added", makerspace=space, target=player,
                         meta={"name": player.name, "host": player.host_url})
        return Response(_player_row(player), status=201)


class AnthiasPlayerDetailView(StaffPresenceView):
    @extend_schema(tags=["Space displays"], request=AnthiasPlayerWriteSerializer, responses={200: AnthiasPlayerSerializer, **ERRORS})
    def patch(self, request, makerspace_id, pk):
        space = _space(request, makerspace_id)
        serializer = AnthiasPlayerWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        with tenant_write(space.pk):
            require_staff(request.user, space, settings=True)
            player = _player(space, pk)
            _apply(player, data)
            player.save()
            audit.record(request.user, "presence.anthias_player_updated", makerspace=space, target=player,
                         meta={"fields": sorted(data)})
        return Response(_player_row(player))

    @extend_schema(tags=["Space displays"], request=None, responses={204: None, **ERRORS},
                   description="Removes the player and, best effort, the web assets SpaceWorks created on it.")
    def delete(self, request, makerspace_id, pk):
        space = _space(request, makerspace_id)
        with tenant_write(space.pk):
            require_staff(request.user, space, settings=True)
            player = _player(space, pk)
            anthias_sync.remove_player_assets(player)
            with transaction.atomic():
                audit.record(request.user, "presence.anthias_player_removed", makerspace=space, target=player,
                             meta={"name": player.name})
                player.delete()
        return Response(status=204)


class AnthiasPlayerTestView(StaffPresenceView):
    throttle_classes = ANTHIAS_PLAYER_THROTTLES  # per account on top of the baseline (336(c)/(g))

    @extend_schema(tags=["Space displays"], request=None, responses={200: AnthiasTestSerializer, **ERRORS},
                   description="Health check: reaches the player, detects its API (v2, else v1.2) and version. "
                               "Failure is a 200 with `ok: false` and a reason code, never a 5xx. Only reasons decided before "
                               "any connection are distinct (`invalid_host`, `dns_failed`, `blocked_address`, "
                               "`private_address`); everything the player did is `failed`. Throttled per user.")
    def post(self, request, makerspace_id, pk):
        space = _space(request, makerspace_id)
        player = _player(space, pk)
        ok, reason, api, version = anthias_sync.test_player(player)
        if not ok:
            logger.info("anthias_test_failed", extra={"player_id": player.pk, "reason": reason})
        reason = coarse_reason(reason)
        audit.record(request.user, "presence.anthias_tested", makerspace=space, target=player, meta={"ok": ok, "error": reason})
        return Response({"ok": ok, "reason": reason, "api_version": api, "anthias_version": version})


class AnthiasPlayerSyncView(StaffPresenceView):
    throttle_classes = ANTHIAS_PLAYER_THROTTLES  # per account on top of the baseline (336(c)/(g))

    @extend_schema(tags=["Space displays"], request=None, responses={200: AnthiasPlayerSerializer, **ERRORS},
                   description="Sync now: creates, updates and deletes this player's web assets to match its screens.")
    def post(self, request, makerspace_id, pk):
        space = _space(request, makerspace_id)
        player = anthias_sync.sync_player(_player(space, pk), actor=request.user)
        return Response(_player_row(player))


class DisplayPlayersView(StaffPresenceView):
    @extend_schema(tags=["Space displays"], request=DisplayPlayersSerializer, responses={200: DisplayAdminSerializer, **ERRORS},
                   description="Choose which players show this screen; their assets are synced after the change.")
    def put(self, request, makerspace_id, pk):
        space = _space(request, makerspace_id)
        serializer = DisplayPlayersSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not display_enabled(space):
            raise feature_off("presence.public_display")
        row = set_players(request.user, space, pk, serializer.validated_data["player_ids"])
        return Response(_row(row, timezone.now()))
