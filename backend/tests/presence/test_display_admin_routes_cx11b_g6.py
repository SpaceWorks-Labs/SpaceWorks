"""Staff display commands exercise real pairing, secret rotation, M2M and retirement."""
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.makerspaces.secrets import encrypt_value, decrypt_value
from apps.presence.display_pairing import digest
from apps.presence.models_anthias import AnthiasPlayer
from apps.presence.models_display import DisplayScreen
from tests.notifications.routes_support_cx11b_g6 import cycle, hidden, send, world

pytestmark = [pytest.mark.django_db, pytest.mark.area_presence]
OPS = [("list", "get", "admin-presence-displays"), ("claim", "post", "admin-presence-displays"),
       ("provision", "post", "admin-presence-display-link"), ("rotate", "post", "admin-presence-display-rotate"),
       ("patch", "patch", "admin-presence-display-detail"), ("delete", "delete", "admin-presence-display-detail"),
       ("players", "put", "admin-presence-display-players")]
CASES = [(op, key, native) for op in OPS for key in ["presence", "presence.public_display",
         *(["display.anthias_push"] if op[0] == "players" else [])] for native in (False, True)]


@pytest.mark.parametrize("op,key,native", CASES)
def test_display_command_effect_audit_and_standing_survive_switch(op, key, native, settings, monkeypatch):
    settings.PUBLIC_APP_BASE_URL = "https://g6.example.test"
    space, actor, client, stranger, foreign = world(native, staff=True)
    now = timezone.now()
    monkeypatch.setattr(timezone, "now", lambda: now)
    screen = DisplayScreen.objects.create(makerspace=None if op[0] == "claim" else space,
        token_digest=digest("old-g6-secret"), link_secret_enc=encrypt_value("old-g6-secret"),
        pairing_code="ABCDEF" if op[0] == "claim" else "", code_expires_at=now + timedelta(minutes=30),
        claimed_at=None if op[0] == "claim" else now, name="G6 retained screen", panels=["announcement"])
    player = AnthiasPlayer.objects.create(makerspace=space, name="G6 linked player", host_url="https://player.example.test")
    name, method, route = op
    kwargs = {"makerspace_id": space.pk}
    if name in {"rotate", "patch", "delete", "players"}:
        kwargs["pk"] = screen.pk
    body = {"code": "ABCDEF", "name": "G6 claimed screen", "panels": ["announcement"]} if name == "claim" else (
        {"name": "G6 changed screen", "panels": ["announcement"], "announcement": "G6 notice"}
        if name in {"patch", "provision"} else {"player_ids": [player.pk]} if name == "players" else {})
    url = reverse(route, kwargs=kwargs)
    def check(response):
        screen.refresh_from_db()
        if name == "list":
            assert response.data["enabled"] is True
            assert [(r["id"], r["name"], r["url"]) for r in response.data["displays"]] == [(screen.pk, "G6 retained screen", "")]
        elif name == "claim":
            assert (screen.makerspace_id, screen.pairing_code, screen.claimed_at, screen.name) == (
                space.pk, "", now, "G6 claimed screen")
            assert response.data["id"] == screen.pk
        elif name == "provision":
            saved = DisplayScreen.objects.get(pk=response.data["id"])
            assert DisplayScreen.objects.count() == 2
            assert (saved.makerspace_id, saved.name, saved.announcement, saved.panels) == (
                space.pk, "G6 changed screen", "G6 notice", ["announcement"])
            secret = response.data["url"].split("#k=")[1]
            assert saved.token_digest == digest(secret)
            assert decrypt_value(saved.link_secret_enc) == secret
        elif name == "rotate":
            secret = response.data["url"].split("#k=")[1]
            assert screen.token_digest == digest(secret) and screen.token_digest != digest("old-g6-secret")
            assert decrypt_value(screen.link_secret_enc) == secret
        elif name == "patch":
            assert (screen.name, screen.announcement, screen.config_version) == ("G6 changed screen", "G6 notice", 2)
            assert response.data["id"] == screen.pk
        elif name == "delete":
            assert screen.revoked_at == now
        else:
            assert list(screen.players.values_list("pk", flat=True)) == [player.pk]
            assert response.data["player_ids"] == [player.pk]
    action = {"claim": "presence.display_claimed", "provision": "presence.display_provisioned",
              "rotate": "presence.display_link_rotated", "patch": "presence.display_updated",
              "delete": "presence.display_unpaired", "players": "presence.display_players_changed"}.get(name)
    fallback = key == "presence.public_display" and name in {"list", "delete"}
    on = (201 if name in {"claim", "provision"} else 204 if name == "delete" else 200, None)
    def off_check(response):
        if name == "list":
            assert response.data["enabled"] is False
            assert [r["id"] for r in response.data["displays"]] == [screen.pk]
        else:
            check(response)
    cycle(space, key, lambda: send(client, method, url, body), check, on=on,
          off=on if fallback else (404, "feature_disabled" if name == "players" and key != "presence" else "not_found"),
          off_check=off_check if fallback else None, off_mutates=fallback and name == "delete",
          actions=(action,) if action else (), probes=[hidden(lambda: send(foreign, method, url, body), native_staff=native)])
