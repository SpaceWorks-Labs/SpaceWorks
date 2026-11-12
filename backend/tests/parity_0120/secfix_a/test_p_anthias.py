"""SECFIX-A: Anthias on the shared transport (lead 2, arch 9, security review M2 / decision 336(g)).

Bounded replies, response-shape checks inside the client, the deployment's own networks always refused, the
stored password cleared when the host changes, coarse Test reasons and a per-user throttle.
"""
from ipaddress import ip_network

import httpx
import pytest

from apps import outbound_http
from apps.audit.models import AuditLog
from apps.outbound_throttles import AnthiasPlayerThrottle
from apps.presence import anthias_client, anthias_networks
from apps.presence.anthias_client import AnthiasClient, AnthiasError
from apps.presence.models_anthias import AnthiasPlayer
from tests.parity_0120.space_display.conftest import isolate, lane  # noqa: F401 - fixtures
from tests.parity_0120.space_display.test_anthias import FakeAnthias, route_through

pytestmark = pytest.mark.django_db
HOST = "http://192.168.1.20"


def _player(**extra):
    fields = {"host_url": "http://player.lan", "username": "", "api_version": "v2", "get_password": lambda self: ""}
    fields.update(extra)
    return type("P", (), fields)()


@pytest.fixture
def lan(monkeypatch, settings):
    settings.ANTHIAS_ALLOW_PRIVATE_HOSTS = True
    monkeypatch.setattr(anthias_client.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("192.168.1.20", 80))])
    monkeypatch.setattr(anthias_client, "service_networks", lambda: ())


@pytest.fixture
def space(lane, lan):  # noqa: F811
    lane.space.enabled_features = sorted(set(lane.space.enabled_features) | {"display.anthias_push"})
    lane.space.save(update_fields=["enabled_features"])
    return lane


def _admin(space, tail=""):
    return f"/api/v1/admin/makerspace/{space.pk}/{tail}"


# --- the client --------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("reply", [httpx.Response(200, json=[]), httpx.Response(200, json="x"),
                                   httpx.Response(200, json={"asset_id": None}),
                                   httpx.Response(200, json={"asset_id": {"nested": 1}}),
                                   httpx.Response(200, json={"asset_id": "../../x"})])
def test_a_malformed_create_answer_is_bad_response_never_a_type_error(lan, monkeypatch, reply):
    route_through(monkeypatch, lambda request: reply)
    with pytest.raises(AnthiasError) as caught:
        AnthiasClient(_player()).create({"is_enabled": True, "skip_asset_check": False, "duration": 5})
    assert caught.value.reason == "bad_response"


def test_a_non_list_asset_answer_is_not_anthias(lan, monkeypatch):
    route_through(monkeypatch, lambda request: httpx.Response(200, json={"not": "a list"}))
    with pytest.raises(AnthiasError) as caught:
        AnthiasClient(_player(api_version="")).detect()
    assert caught.value.reason == "bad_response"


def test_a_malformed_info_answer_only_blanks_the_version(lan, monkeypatch):
    route_through(monkeypatch, lambda request: httpx.Response(
        200, json=[] if request.url.path.endswith("/assets") else ["not", "an", "object"]))
    assert AnthiasClient(_player(api_version="")).detect() == ("v2", "")


def test_a_well_formed_create_answer_works(lan, monkeypatch):
    route_through(monkeypatch, lambda request: httpx.Response(201, json={"asset_id": "a7"}))
    assert AnthiasClient(_player()).create({"is_enabled": True, "skip_asset_check": False, "duration": 5}) == "a7"


def test_the_client_asks_the_transport_for_a_byte_cap_and_a_deadline(lan, monkeypatch):
    seen = {}

    def send(target, method, **kwargs):
        seen.update(kwargs, ip=target.addresses[0].ip)
        return outbound_http.Response(200, {}, b"[]")
    monkeypatch.setattr(outbound_http, "send", send)
    AnthiasClient(_player())._request("GET", "/api/v2/assets")
    assert seen["max_bytes"] == anthias_client.BODY_LIMIT and seen["deadline"] == anthias_client.TOTAL_SECONDS
    assert seen["ip"] == "192.168.1.20"


def test_an_oversized_reply_is_an_anthias_error(lan, monkeypatch):
    def send(*_a, **_k):
        raise outbound_http.OutboundError("too_large")
    monkeypatch.setattr(outbound_http, "send", send)
    with pytest.raises(AnthiasError) as caught:
        AnthiasClient(_player())._request("GET", "/api/v2/assets")
    assert caught.value.reason == "http_error"


# --- addresses ---------------------------------------------------------------------------------------------------
def test_the_deployments_own_network_is_refused_even_with_private_lan_allowed(monkeypatch, settings):
    settings.ANTHIAS_ALLOW_PRIVATE_HOSTS = True
    monkeypatch.setattr(anthias_client, "service_networks", lambda: (ip_network("172.18.0.0/16"),))
    monkeypatch.setattr(anthias_client.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("172.18.0.4", 9000))])
    with pytest.raises(AnthiasError) as caught:
        anthias_client.resolve_target("http://minio:9000")
    assert caught.value.reason == "blocked_address"
    monkeypatch.setattr(anthias_client.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("192.168.1.20", 80))])
    assert anthias_client.resolve_target("http://player.lan")[0] == "http://192.168.1.20:80"


def test_cgnat_metadata_is_refused_and_cgnat_needs_the_private_allowance(monkeypatch, settings):
    monkeypatch.setattr(anthias_client, "service_networks", lambda: ())
    settings.ANTHIAS_ALLOW_PRIVATE_HOSTS = False
    monkeypatch.setattr(anthias_client.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("100.64.0.9", 80))])
    with pytest.raises(AnthiasError) as caught:
        anthias_client.resolve_target("http://player.lan")
    assert caught.value.reason == "private_address"


def test_directly_connected_container_networks_are_read_from_the_route_table(tmp_path):
    routes = tmp_path / "route"
    routes.write_text(
        "Iface\tDestination\tGateway\tFlags\tRefCnt\tUse\tMetric\tMask\tMTU\tWindow\tIRTT\n"
        "eth0\t00000000\t010012AC\t0003\t0\t0\t0\t00000000\t0\t0\t0\n"  # default route via 172.18.0.1: not blocked
        "eth0\t000012AC\t00000000\t0001\t0\t0\t0\t0000FFFF\t0\t0\t0\n")  # 172.18.0.0/16 directly connected
    marker = tmp_path / ".dockerenv"
    assert anthias_networks._connected(str(routes), str(marker)) == []  # not in a container: nothing guessed
    marker.write_text("")
    assert anthias_networks._connected(str(routes), str(marker)) == [ip_network("172.18.0.0/16")]


def test_operator_listed_networks_are_blocked(settings):
    settings.OUTBOUND_BLOCKED_NETWORKS = ["10.20.0.0/16", "not-a-cidr"]
    assert anthias_networks._configured() == [ip_network("10.20.0.0/16")]


# --- the staff routes --------------------------------------------------------------------------------------------
def _create(space, **extra):
    admin = space.client(space.staff)
    pid = admin.post(_admin(space.space, "anthias-players"),
                     {"name": "Pi", "host_url": HOST, "username": "pi", "password": "hunter2", **extra},
                     format="json").json()["id"]
    return admin, pid


def test_changing_the_host_clears_the_stored_password(space):
    admin, pid = _create(space)
    row = admin.patch(_admin(space.space, f"anthias-players/{pid}"), {"host_url": "http://192.168.1.99"},
                      format="json").json()
    assert row["has_password"] is False and AnthiasPlayer.objects.get(pk=pid).get_password() == ""


def test_the_password_survives_other_edits_and_a_new_one_with_the_new_host(space):
    admin, pid = _create(space)
    admin.patch(_admin(space.space, f"anthias-players/{pid}"), {"name": "Renamed", "host_url": HOST}, format="json")
    assert AnthiasPlayer.objects.get(pk=pid).get_password() == "hunter2"
    admin.patch(_admin(space.space, f"anthias-players/{pid}"),
                {"host_url": "http://192.168.1.99", "password": "fresh"}, format="json")
    assert AnthiasPlayer.objects.get(pk=pid).get_password() == "fresh"


def test_test_reports_only_coarse_reasons(space, monkeypatch):
    admin, pid = _create(space)
    login_page = lambda request: httpx.Response(302, headers={"location": "/login/"})  # noqa: E731 - wrong login
    server_error = lambda request: httpx.Response(500)  # noqa: E731
    for fake in (FakeAnthias("v2", down=True), login_page, server_error, FakeAnthias("v9")):
        route_through(monkeypatch, fake)
        result = admin.post(_admin(space.space, f"anthias-players/{pid}/test")).json()
        assert result["ok"] is False and result["reason"] == "failed"
    meta = AuditLog.objects.filter(action="presence.anthias_tested").values_list("meta", flat=True)
    assert {m["error"] for m in meta} == {"failed"}
    route_through(monkeypatch, FakeAnthias("v2"))
    assert admin.post(_admin(space.space, f"anthias-players/{pid}/test")).json()["ok"] is True


def test_address_problems_found_before_any_connection_stay_distinct(space, monkeypatch, settings):
    admin, pid = _create(space)
    settings.ANTHIAS_ALLOW_PRIVATE_HOSTS = False
    assert admin.post(_admin(space.space, f"anthias-players/{pid}/test")).json()["reason"] == "private_address"


def test_test_and_sync_are_throttled_per_user(space, monkeypatch):
    admin, pid = _create(space)
    route_through(monkeypatch, FakeAnthias("v2"))
    monkeypatch.setattr(AnthiasPlayerThrottle, "default_rate", "2/min")
    from django.core.cache import cache
    cache.clear()
    codes = [admin.post(_admin(space.space, f"anthias-players/{pid}/test")).status_code for _ in range(3)]
    assert codes == [200, 200, 429]
    assert admin.post(_admin(space.space, f"anthias-players/{pid}/sync")).status_code == 429
