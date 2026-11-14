"""Anthias switch callers retain real services; only remote player I/O is replaced."""
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.makerspaces.secrets import encrypt_value
from apps.presence import anthias_sync
from apps.presence.display_pairing import digest
from apps.presence.models_anthias import AnthiasAssetLink, AnthiasPlayer
from apps.presence.models_display import DisplayScreen
from tests.notifications.routes_support_cx11b_g6 import cycle, hidden, send, world

pytestmark = [pytest.mark.django_db, pytest.mark.area_presence]
OPS = [("list", "get", "admin-anthias-players"), ("create", "post", "admin-anthias-players"),
       ("patch", "patch", "admin-anthias-player"), ("delete", "delete", "admin-anthias-player"),
       ("test", "post", "admin-anthias-player-test"), ("sync", "post", "admin-anthias-player-sync")]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["presence", "display.anthias_push"])
@pytest.mark.parametrize("op", OPS)
def test_anthias_route_persists_exact_effect_and_never_contacts_foreign_player(op, key, native, settings, monkeypatch):
    settings.PUBLIC_APP_BASE_URL = "https://g6.example.test"
    space, actor, client, stranger, foreign = world(native, staff=True)
    now = timezone.now()
    monkeypatch.setattr(timezone, "now", lambda: now)
    player = AnthiasPlayer.objects.create(makerspace=space, name="G6 retained player", host_url="https://player.example.test")
    screen = DisplayScreen.objects.create(makerspace=space, name="G6 screen", token_digest=digest("g6-screen-secret"),
        link_secret_enc=encrypt_value("g6-screen-secret"), code_expires_at=now, claimed_at=now, panels=["announcement"])
    screen.players.add(player)
    name, method, route = op
    calls = []
    class RemotePlayer:
        def __init__(self, selected):
            assert selected.pk == player.pk
        def detect(self):
            calls.append(("detect",))
            return "v2", "g6-version"
        def create(self, payload):
            calls.append(("create", payload))
            return "g6-asset-id"
        def delete(self, asset_id):
            calls.append(("delete", asset_id))
        def update(self, asset_id, payload):
            calls.append(("update", asset_id, payload))
    monkeypatch.setattr(anthias_sync, "AnthiasClient", RemotePlayer)
    if name == "delete":
        AnthiasAssetLink.objects.create(player=player, display=screen, asset_id="old-g6-asset")
    kwargs = {"makerspace_id": space.pk}
    if name not in {"list", "create"}:
        kwargs["pk"] = player.pk
    url = reverse(route, kwargs=kwargs)
    body = {"name": "G6 new player", "host_url": "https://new-player.example.test", "password": "G6 remote password"} if name == "create" else (
        {"name": "G6 renamed player"} if name == "patch" else {})
    def check(response):
        if name == "delete":
            assert not AnthiasPlayer.objects.filter(pk=player.pk).exists()
            assert not AnthiasAssetLink.objects.exists()
            assert calls == [("detect",), ("delete", "old-g6-asset")]
            return
        player.refresh_from_db()
        if name == "list":
            assert response.data["enabled"] is True
            assert [(r["id"], r["name"], r["host_url"]) for r in response.data["players"]] == [
                (player.pk, "G6 retained player", "https://player.example.test")]
        elif name == "create":
            saved = AnthiasPlayer.objects.get(pk=response.data["id"])
            assert AnthiasPlayer.objects.count() == 2
            assert (saved.name, saved.host_url, saved.get_password(), saved.makerspace_id) == (
                "G6 new player", "https://new-player.example.test", "G6 remote password", space.pk)
            assert saved.password_enc != "G6 remote password" and "password" not in response.data
        elif name == "patch":
            assert player.name == "G6 renamed player"
            assert response.data["id"] == player.pk
        elif name == "test":
            assert response.data == {"ok": True, "reason": "", "api_version": "v2", "anthias_version": "g6-version"}
            assert (player.api_version, player.anthias_version) == ("v2", "g6-version")
            assert calls == [("detect",)]
        else:
            assert (player.status, player.last_error, player.last_synced_at) == ("ok", "", now)
            link = AnthiasAssetLink.objects.get(player=player, display=screen)
            assert link.asset_id == "g6-asset-id"
            assert calls[0] == ("detect",) and len(calls) == 2
            assert calls[1][0] == "create"
            assert calls[1][1]["uri"] == "https://g6.example.test/display#k=g6-screen-secret"
            assert calls[1][1]["name"] == f"SpaceWorks: G6 screen (#{screen.pk})"
            assert response.data["id"] == player.pk and response.data["status"] == "ok"
        if name not in {"sync", "test"}:
            assert calls == []
    action = {"create": "presence.anthias_player_added", "patch": "presence.anthias_player_updated",
              "delete": "presence.anthias_player_removed", "test": "presence.anthias_tested", "sync": "presence.anthias_synced"}.get(name)
    def foreign_call():
        before = list(calls)
        response = send(foreign, method, url, body)
        assert calls == before
        return response
    fallback = name == "list" and key == "display.anthias_push"
    def off_check(response):
        assert response.data["enabled"] is False and response.data["players"] == []
        assert calls == []
    cycle(space, key, lambda: send(client, method, url, body), check,
          on=(201 if name == "create" else 204 if name == "delete" else 200, None),
          off=(200, None) if fallback else (404, "not_found" if key == "presence" else "feature_disabled"),
          off_check=off_check if fallback else None, prepare=calls.clear,
          actions=(action,) if action else (), probes=[hidden(foreign_call, native_staff=native)])
