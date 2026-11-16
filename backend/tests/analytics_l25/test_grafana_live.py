"""Decision 263: test-connection (Grafana mocked), the private-address rule, and embeds that
stay inside their own space: a space's URL, token, organization and listed uids only."""

import socket

import pytest
from django.test import override_settings

from apps.analytics import grafana_client
from apps.audit.models import AuditLog

from .grafana_helpers import PUBLIC_TOKEN, TOKEN, FakeGrafana, configure, g_platform_url, g_space_url
from .helpers import client_for, manager, space, superadmin

pytestmark = pytest.mark.django_db


@pytest.fixture
def grafana(monkeypatch):
    fake = FakeGrafana()
    monkeypatch.setattr(grafana_client, "fetch", fake)
    return fake


def test_a_working_connection_reports_both_checks(grafana):
    makerspace = space()
    configure(makerspace)
    response = client_for(manager(makerspace)).post(g_space_url("-test", makerspace))
    assert response.status_code == 200, response.data
    assert response.data["ok"] is True and response.data["version"] == "11.3.0"
    assert response.data["dashboards_found"] == 2
    assert [check["name"] for check in response.data["checks"]] == ["health", "search"]
    health, search = grafana.calls
    assert health["path"] == "/api/health" and health["token"] == ""
    assert search["path"] == "/api/search" and search["token"] == TOKEN and search["org_id"] == 3
    assert search["allow_private"] is False
    entry = AuditLog.objects.get(makerspace=makerspace, action="analytics.grafana_connection_tested")
    assert entry.meta == {"scope": "space", "ok": True}


def test_a_refused_token_is_reported_not_raised(monkeypatch):
    fake = FakeGrafana(responses={
        "/api/health": (200, "application/json", b'{"database":"ok","version":"11"}'),
        "/api/search": (401, "application/json", b'{"message":"invalid API key"}')})
    monkeypatch.setattr(grafana_client, "fetch", fake)
    makerspace = space()
    configure(makerspace)
    data = client_for(manager(makerspace)).post(g_space_url("-test", makerspace)).data
    assert data["ok"] is False and data["checks"][1]["ok"] is False
    assert "invalid API key" not in str(data)


def test_an_unreachable_grafana_is_a_typed_result(monkeypatch):
    monkeypatch.setattr(grafana_client, "fetch", FakeGrafana(error="timeout"))
    makerspace = space()
    configure(makerspace)
    data = client_for(manager(makerspace)).post(g_space_url("-test", makerspace)).data
    assert data["ok"] is False and data["checks"] == [{"name": "health", "ok": False, "detail": data["checks"][0]["detail"]}]


def test_no_url_is_a_typed_conflict(grafana):
    makerspace = space()
    configure(makerspace, url="")
    response = client_for(manager(makerspace)).post(g_space_url("-test", makerspace))
    assert response.status_code == 409 and response.data["code"] == "grafana_not_configured"
    assert grafana.calls == []


def _resolves_to(monkeypatch, address):
    monkeypatch.setattr(grafana_client, "_getaddrinfo",
                        lambda host, port: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port))])


@pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.5", "169.254.169.254", "192.168.1.9"])
def test_a_space_may_not_point_the_server_at_a_private_address(monkeypatch, address):
    _resolves_to(monkeypatch, address)
    with pytest.raises(grafana_client.GrafanaUnreachable) as error:
        grafana_client.check_host("http://grafana:3000", allow_private=False)
    assert error.value.reason == "private_address"
    grafana_client.check_host("http://grafana:3000", allow_private=True)


def test_private_hosts_follow_the_scope_and_the_operator_switch():
    from apps.analytics.access import Scope

    makerspace = space()
    assert grafana_client.private_hosts_allowed(Scope(None)) is True
    assert grafana_client.private_hosts_allowed(Scope(makerspace)) is False
    with override_settings(GRAFANA_ALLOW_PRIVATE_HOSTS=True):
        assert grafana_client.private_hosts_allowed(Scope(makerspace)) is True


def test_a_public_embed_is_this_spaces_own_dashboard_only(grafana):
    a, b = space(), space()
    configure(a)
    configure(b, url="https://grafana-b.example.org",
              boards=[{"uid": "b-only", "title": "B", "mode": "public", "public_token": "f" * 32}])
    client = client_for(manager(a))
    response = client.get(g_space_url("-embed", a, "sw-inv"))
    assert response.status_code == 200, response.data
    assert response.data == {"mode": "public", "url": f"https://grafana.example.org/public-dashboards/{PUBLIC_TOKEN}"}
    refused = client.get(g_space_url("-embed", a, "b-only"))
    assert refused.status_code == 409 and refused.data["code"] == "grafana_dashboard_unknown"
    assert client_for(manager(a)).get(g_space_url("-embed", b, "b-only")).status_code == 404
    assert client.get(g_space_url("-embed", a, "sw-mach")).data["code"] == "grafana_dashboard_unknown"
    assert AuditLog.objects.filter(makerspace=a, action="analytics.grafana_dashboard_viewed").count() == 1


def test_a_render_uses_this_spaces_token_and_organization(grafana):
    a, b = space(), space()
    configure(a)
    configure(b, url="https://grafana-b.example.org", token="glsa_space_b_token_value")
    response = client_for(manager(a)).get(g_space_url("-render", a, "sw-mach"), {"width": 99999, "theme": "dark"})
    assert response.status_code == 200 and response["Content-Type"] == "image/png"
    call = grafana.calls[-1]
    assert call["base_url"] == "https://grafana.example.org" and call["path"] == "/render/d/sw-mach"
    assert call["token"] == TOKEN and call["org_id"] == 3
    assert call["params"]["width"] == 3840 and call["params"]["theme"] == "dark"


def test_a_render_failure_is_typed(monkeypatch):
    monkeypatch.setattr(grafana_client, "fetch", FakeGrafana(responses={"render": (500, "text/html", b"boom")}))
    makerspace = space()
    configure(makerspace)
    response = client_for(manager(makerspace)).get(g_space_url("-render", makerspace, "sw-mach"))
    assert response.status_code == 409 and response.data["code"] == "grafana_unreachable"


def test_the_platform_embed_uses_the_platform_connection_only(grafana):
    makerspace = space()
    configure(makerspace)
    configure(None, url="https://grafana-platform.example.org",
              boards=[{"uid": "plat", "title": "P", "mode": "public", "public_token": "e" * 32}])
    root = client_for(superadmin())
    assert root.get(g_platform_url("-embed", "plat")).data["url"].startswith("https://grafana-platform.example.org/")
    assert root.get(g_platform_url("-embed", "sw-inv")).data["code"] == "grafana_dashboard_unknown"
