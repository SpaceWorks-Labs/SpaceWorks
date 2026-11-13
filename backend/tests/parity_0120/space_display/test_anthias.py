"""Decision 325c: Anthias players, the SSRF rules, and idempotent asset sync against a mocked player."""
import json

import httpx
import pytest

from apps import outbound_http
from apps.audit.models import AuditLog
from apps.presence import anthias_client, anthias_sync
from apps.presence.anthias_client import AnthiasClient, AnthiasError, clean_host, resolve_target
from apps.presence.models_anthias import AnthiasAssetLink, AnthiasPlayer

pytestmark = pytest.mark.django_db
HOST = "http://192.168.1.20"


def _typed(version, body):
    """The field types the real serializers accept (Screenly/Anthias 6a8202b, api/serializers/v2.py, v1_2.py)."""
    if version == "v2":
        ok = (isinstance(body["is_enabled"], bool) and isinstance(body["skip_asset_check"], bool)
              and isinstance(body["nocache"], bool) and type(body["duration"]) is int)
    else:
        ok = (all(type(body[k]) is int for k in ("is_enabled", "skip_asset_check", "nocache", "is_processing"))
              and isinstance(body["duration"], str))
    return ok and body["mimetype"] == "webpage" and body["start_date"].endswith("Z") and isinstance(body["play_order"], int)


class FakeAnthias:
    """An in-memory player: v2 or v1.2, optional basic auth (unauthenticated = 302 to login, like Anthias)."""

    def __init__(self, version="v2", auth=None, down=False):
        self.version, self.auth, self.down, self.assets, self.calls, self.next_id = version, auth, down, {}, [], 1

    def __call__(self, request):
        self.calls.append((request.method, request.url.path))
        if self.down:
            raise httpx.ConnectError("down")
        if self.auth and request.headers.get("authorization") is None:
            return httpx.Response(302, headers={"location": "/login/?next=/api"})
        path = request.url.path
        if not path.startswith(f"/api/{self.version}/"):
            return httpx.Response(404)
        if path.endswith("/info"):  # only v2 has /info, and its version key is `anthias_version`
            return httpx.Response(200, json={"anthias_version": "0.19.1"})
        if path.endswith("/assets") and request.method == "GET":
            return httpx.Response(200, json=list(self.assets.values()))
        if path.endswith("/assets") and request.method == "POST":
            body = json.loads(request.content)
            if not _typed(self.version, body) or any(a["name"] == body["name"] for a in self.assets.values()):
                return httpx.Response(400)
            asset_id = f"a{self.next_id}"
            self.next_id += 1
            self.assets[asset_id] = {**body, "asset_id": asset_id}
            return httpx.Response(201, json={"asset_id": asset_id})
        asset_id = path.rsplit("/", 1)[1]
        if asset_id not in self.assets:
            return httpx.Response(404)
        if request.method == "DELETE":
            del self.assets[asset_id]
            return httpx.Response(204)
        body = json.loads(request.content)
        if not _typed(self.version, body):
            return httpx.Response(400)
        body.pop("uri", None)  # the real update serializer has no uri (nor mimetype): they cannot change
        self.assets[asset_id] = {**self.assets[asset_id], **body}
        return httpx.Response(200, json=self.assets[asset_id])


def route_through(monkeypatch, handler):
    """Serve the shared outbound transport (apps.outbound_http.send) from an httpx-style handler.

    The request URL carries the PINNED address and the Host header the original name, exactly what goes on the
    wire; a handler that raises httpx.ConnectError is an unreachable player.
    """
    def send(target, method, *, body=None, headers=None, **_limits):
        ip = target.addresses[0].ip
        literal = f"[{ip}]" if ":" in ip else ip
        request = httpx.Request(method, f"{target.scheme}://{literal}:{target.port}{target.request_target}",
                                content=body or b"", headers={**(headers or {}), "Host": target.host_header})
        try:
            response = handler(request)
        except httpx.ConnectError:
            raise outbound_http.OutboundError("unreachable") from None
        response.read()
        return outbound_http.Response(response.status_code, {k.lower(): v for k, v in response.headers.items()},
                                      response.content)

    monkeypatch.setattr(outbound_http, "send", send)


@pytest.fixture(autouse=True)
def no_service_networks(monkeypatch):
    """The test host's own networks are not what these tests are about (see test_secfix_a for that rule)."""
    monkeypatch.setattr(anthias_client, "service_networks", lambda: ())


@pytest.fixture
def anthias(lane, monkeypatch, settings):
    settings.PUBLIC_APP_BASE_URL = "https://spaces.example.test"
    lane.space.enabled_features = sorted(set(lane.space.enabled_features) | {"display.anthias_push"})
    lane.space.save(update_fields=["enabled_features"])
    monkeypatch.setattr(anthias_client.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("192.168.1.20", 80))])
    state = {}

    def install(fake):
        state["fake"] = fake
        route_through(monkeypatch, fake)
        return fake

    lane.install = install
    return lane


def _admin(space, tail=""):
    return f"/api/v1/admin/makerspace/{space.pk}/{tail}"


def _screen(lane):
    admin = lane.client(lane.staff)
    body = admin.post(_admin(lane.space, "presence-displays/link"), {"name": "Lobby", "layout": "playlist",
                                                                    "slide_seconds": {"here_now": 20, "calendar": 10}}, format="json").json()
    return admin, body


def _player(lane, admin, **extra):
    return admin.post(_admin(lane.space, "anthias-players"), {"name": "Pi 1", "host_url": HOST, **extra}, format="json")


def test_link_screen_url_works_and_secret_is_not_in_state(anthias):
    admin, screen = _screen(anthias)
    assert screen["url"].startswith("https://spaces.example.test/display#k=")
    token = screen["url"].split("#k=")[1]
    state = anthias.client().get(f"/api/v1/space-displays/{token}/state/").json()
    assert state["state"] == "paired" and state["config"]["layout"] == "playlist"
    assert "k=" not in json.dumps(state)


def test_player_password_is_encrypted_and_never_returned(anthias):
    admin, _ = _screen(anthias)
    created = _player(anthias, admin, username="pi", password="hunter2").json()
    assert created["has_password"] is True and "password" not in created and "hunter2" not in json.dumps(created)
    row = AnthiasPlayer.objects.get()
    assert "hunter2" not in row.password_enc and row.get_password() == "hunter2"
    listing = admin.get(_admin(anthias.space, "anthias-players")).json()
    assert "hunter2" not in json.dumps(listing) and listing["allow_private_hosts"] is True


def test_switch_off_is_404(lane):
    admin = lane.client(lane.staff)
    assert admin.post(_admin(lane.space, "anthias-players"), {"name": "x", "host_url": HOST}, format="json").status_code == 404


def test_bad_host_rejected(anthias):
    admin = anthias.client(anthias.staff)
    for bad in ("ftp://x", "http://user:pw@x", "http://x/path", "not a url"):
        assert _player(anthias, admin, host_url=bad).status_code == 400


def test_test_connection_detects_version(anthias):
    admin, _ = _screen(anthias)
    pid = _player(anthias, admin).json()["id"]
    anthias.install(FakeAnthias("v1.2"))
    result = admin.post(_admin(anthias.space, f"anthias-players/{pid}/test")).json()
    assert result == {"ok": True, "reason": "", "api_version": "v1.2", "anthias_version": ""}  # v1.2 reports no version
    anthias.install(FakeAnthias("v2"))
    assert admin.post(_admin(anthias.space, f"anthias-players/{pid}/test")).json()["anthias_version"] == "0.19.1"


def test_sync_creates_updates_is_idempotent_and_deletes(anthias):
    admin, screen = _screen(anthias)
    pid = _player(anthias, admin).json()["id"]
    fake = anthias.install(FakeAnthias("v2"))
    assert admin.put(_admin(anthias.space, f"presence-displays/{screen['id']}/players"), {"player_ids": [pid]}, format="json").status_code == 200
    synced = admin.post(_admin(anthias.space, f"anthias-players/{pid}/sync")).json()
    assert synced["status"] == "ok" and synced["api_version"] == "v2"
    asset = next(iter(fake.assets.values()))
    assert asset["mimetype"] == "webpage" and asset["uri"] == screen["url"] and asset["duration"] == 45
    assert asset["is_enabled"] is True and asset["name"] == f"SpaceWorks: Lobby (#{screen['id']})"
    posts = [c for c in fake.calls if c[0] == "POST"]
    admin.post(_admin(anthias.space, f"anthias-players/{pid}/sync"))  # nothing changed
    assert [c for c in fake.calls if c[0] == "POST"] == posts and len(fake.assets) == 1
    admin.patch(_admin(anthias.space, f"presence-displays/{screen['id']}"), {"name": "Front", "slide_seconds": {"here_now": 40}}, format="json")
    admin.post(_admin(anthias.space, f"anthias-players/{pid}/sync"))
    assert len(fake.assets) == 1 and next(iter(fake.assets.values()))["name"] == f"SpaceWorks: Front (#{screen['id']})"
    admin.put(_admin(anthias.space, f"presence-displays/{screen['id']}/players"), {"player_ids": []}, format="json")
    admin.post(_admin(anthias.space, f"anthias-players/{pid}/sync"))
    assert fake.assets == {} and AnthiasAssetLink.objects.count() == 0
    assert AuditLog.objects.filter(action="presence.anthias_synced").count() >= 4


def test_v12_fallback_uses_integer_flags(anthias):
    admin, screen = _screen(anthias)
    pid = _player(anthias, admin).json()["id"]
    fake = anthias.install(FakeAnthias("v1.2"))
    admin.put(_admin(anthias.space, f"presence-displays/{screen['id']}/players"), {"player_ids": [pid]}, format="json")
    assert admin.post(_admin(anthias.space, f"anthias-players/{pid}/sync")).json()["api_version"] == "v1.2"
    asset = next(iter(fake.assets.values()))
    assert asset["is_enabled"] == 1 and asset["duration"] == "45" and asset["skip_asset_check"] == 1


def test_deleted_on_player_is_recreated(anthias):
    admin, screen = _screen(anthias)
    pid = _player(anthias, admin).json()["id"]
    fake = anthias.install(FakeAnthias("v2"))
    admin.put(_admin(anthias.space, f"presence-displays/{screen['id']}/players"), {"player_ids": [pid]}, format="json")
    admin.post(_admin(anthias.space, f"anthias-players/{pid}/sync"))
    fake.assets.clear()
    AnthiasAssetLink.objects.update(synced_hash="stale")
    admin.post(_admin(anthias.space, f"anthias-players/{pid}/sync"))
    assert len(fake.assets) == 1


def test_auth_failure_and_unreachable_are_recorded_not_raised(anthias):
    admin, screen = _screen(anthias)
    pid = _player(anthias, admin).json()["id"]
    admin.put(_admin(anthias.space, f"presence-displays/{screen['id']}/players"), {"player_ids": [pid]}, format="json")
    anthias.install(FakeAnthias("v2", auth=("pi", "x")))
    row = admin.post(_admin(anthias.space, f"anthias-players/{pid}/sync")).json()
    # Decision 336(g): what the player did is not told to the caller (no port/service oracle); the row keeps
    # the fine reason for the server log only.
    assert row["status"] == "error" and row["last_error"] == "failed"
    assert AnthiasPlayer.objects.get(pk=pid).last_error == "auth_failed"
    anthias.install(FakeAnthias("v2", down=True))
    row = admin.post(_admin(anthias.space, f"anthias-players/{pid}/sync")).json()
    assert row["status"] == "error" and row["last_error"] == "failed"
    assert AnthiasPlayer.objects.get(pk=pid).last_error == "unreachable"
    tested = admin.post(_admin(anthias.space, f"anthias-players/{pid}/test")).json()
    assert tested["ok"] is False and tested["reason"] == "failed"


def test_player_of_another_space_is_404(anthias):
    admin, _ = _screen(anthias)
    pid = _player(anthias, admin).json()["id"]
    from apps.makerspaces.models import Makerspace
    other = Makerspace.objects.create(name="Other", slug="other-anthias")
    assert anthias.client(anthias.staff).post(_admin(other, f"anthias-players/{pid}/test")).status_code in (403, 404)


def test_clean_host_normalises():
    assert clean_host(" http://192.168.1.20:5000/ ") == "http://192.168.1.20:5000"
    with pytest.raises(AnthiasError):
        clean_host("javascript:alert(1)")


@pytest.mark.parametrize("address,allow,reason", [
    ("169.254.169.254", True, "blocked_address"), ("127.0.0.1", True, "blocked_address"),
    ("fe80::1", True, "blocked_address"), ("100.100.100.200", True, "blocked_address"),
    ("192.168.1.20", False, "private_address"), ("10.0.0.5", False, "private_address"),
])
def test_ssrf_rules(settings, monkeypatch, address, allow, reason):
    settings.ANTHIAS_ALLOW_PRIVATE_HOSTS = allow
    monkeypatch.setattr(anthias_client.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", (address, 80))])
    with pytest.raises(AnthiasError) as caught:
        resolve_target("http://player.lan")
    assert caught.value.reason == reason


def test_private_lan_allowed_by_default(settings, monkeypatch):
    settings.ANTHIAS_ALLOW_PRIVATE_HOSTS = True
    monkeypatch.setattr(anthias_client.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("192.168.1.20", 80))])
    resolve_target("http://player.lan")


def test_cycle_seconds_covers_the_playlist(anthias):
    _admin_client, screen = _screen(anthias)
    from apps.presence.models_display import DisplayScreen
    row = DisplayScreen.objects.get(pk=screen["id"])
    assert anthias_sync.cycle_seconds(row) == 45  # 3 default panels x 15 s


def test_dns_rebinding_cannot_swap_the_target(settings, monkeypatch):
    """A resolver that answers public first and the metadata IP second: we resolve once and connect to the first."""
    answers = iter([[(2, 1, 6, "", ("93.184.216.34", 80))], [(2, 1, 6, "", ("169.254.169.254", 80))]])
    calls = []
    monkeypatch.setattr(anthias_client.socket, "getaddrinfo", lambda *a, **k: calls.append(a) or next(answers))
    seen = []

    def handler(request):
        seen.append((request.url.host, request.headers["host"]))
        return httpx.Response(200, json=[])

    route_through(monkeypatch, handler)
    client = AnthiasClient(type("P", (), {"host_url": "http://player.example", "username": "", "api_version": "v2",
                                          "get_password": lambda self: ""})())
    client._request("GET", "/api/v2/assets")
    assert seen == [("93.184.216.34", "player.example")] and len(calls) == 1
    with pytest.raises(AnthiasError) as caught:  # a later lookup that returns metadata is refused outright
        client._request("GET", "/api/v2/assets")
    assert caught.value.reason == "blocked_address" and len(seen) == 1


def test_https_pins_ip_and_keeps_sni(monkeypatch):
    monkeypatch.setattr(anthias_client.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 443))])
    pinned, host_header, sni = resolve_target("https://player.example")
    assert (pinned, host_header, sni) == ("https://93.184.216.34:443", "player.example", "player.example")


def test_capability_purge_removes_players_credentials_and_links(anthias):
    from apps.makerspaces.capability_purge_plans import BY_KEY
    from apps.presence.models_display import DisplayScreen
    admin, screen = _screen(anthias)
    pid = _player(anthias, admin, username="pi", password="hunter2").json()["id"]
    row = DisplayScreen.objects.get(pk=screen["id"])
    AnthiasAssetLink.objects.create(player_id=pid, display=row, asset_id="a1")
    plan = BY_KEY["display.anthias_push"]
    assert plan.preview(anthias.space) == {"players": 1, "asset_links": 1}
    result = plan.delete(anthias.space, None)
    assert AnthiasPlayer.objects.count() == 0 and AnthiasAssetLink.objects.count() == 0
    assert DisplayScreen.objects.filter(pk=row.pk).exists()  # screens and their addresses stay
    assert "presence.AnthiasPlayer" in result.model_labels


@pytest.mark.parametrize("version", ["v2", "v1.2"])
def test_new_address_replaces_the_asset_because_uri_cannot_be_updated(anthias, version):
    admin, screen = _screen(anthias)
    pid = _player(anthias, admin).json()["id"]
    fake = anthias.install(FakeAnthias(version))
    admin.put(_admin(anthias.space, f"presence-displays/{screen['id']}/players"), {"player_ids": [pid]}, format="json")
    admin.post(_admin(anthias.space, f"anthias-players/{pid}/sync"))
    old_uri = next(iter(fake.assets.values()))["uri"]
    rotated = admin.post(_admin(anthias.space, f"presence-displays/{screen['id']}/link")).json()
    admin.post(_admin(anthias.space, f"anthias-players/{pid}/sync"))
    assert len(fake.assets) == 1 and next(iter(fake.assets.values()))["uri"] == rotated["url"] != old_uri
