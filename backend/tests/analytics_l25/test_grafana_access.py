"""Decision 263: Grafana gating per role, module off = inert, the platform set superadmin-only,
route classes, and the provider switch hiding one tool without touching the other."""

import pytest

from apps.accounts import rbac
from apps.accounts.delegated_routes import DELEGABLE, MEMBERSHIP_ONLY, PLATFORM_ONLY, route_class
from apps.analytics.models import AnalyticsConnection

from .grafana_helpers import G_MANAGER_ROUTES, G_SPACE_ROUTES, configure, g_platform_url, g_space_url
from .helpers import client_for, inventory_manager, manager, plain_member, space, space_url, superadmin

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("method,name,args", G_SPACE_ROUTES)
def test_module_off_answers_404_on_every_grafana_route(method, name, args):
    makerspace = space(analytics=False)
    for user in (manager(makerspace), superadmin()):
        response = getattr(client_for(user), method)(g_space_url(name, makerspace, *args), {}, format="json")
        assert response.status_code == 404
    assert not AnalyticsConnection.objects.filter(makerspace=makerspace).exists()


@pytest.mark.parametrize("make", [inventory_manager, plain_member])
def test_staff_without_view_analytics_are_refused(make):
    makerspace = space()
    configure(makerspace)
    client = client_for(make(makerspace))
    assert client.get(g_space_url("", makerspace)).status_code == 403
    assert client.get(g_space_url("-embed", makerspace, "sw-inv")).status_code == 403
    assert client.get(g_space_url("-render", makerspace, "sw-mach")).status_code == 403


def test_a_stranger_gets_404():
    makerspace, other = space(), space()
    assert client_for(manager(other)).get(g_space_url("", makerspace)).status_code == 404


def test_space_manager_reads_the_summary_without_tokens():
    makerspace = space()
    configure(makerspace)
    response = client_for(manager(makerspace)).get(g_space_url("", makerspace))
    assert response.status_code == 200, response.data
    assert response.data["configured"] is True and response.data["can_manage"] is True
    assert response.data["dashboards"][0] == {"uid": "sw-inv", "title": "Inventory", "mode": "public"}
    assert "public_token" not in str(response.data) and "0123456789abcdef" not in str(response.data)


def test_view_analytics_alone_views_but_never_manages(monkeypatch):
    makerspace = space()
    configure(makerspace)
    user = inventory_manager(makerspace)
    monkeypatch.setattr(rbac, "can", lambda actor, action, makerspace_id=None:
                        action in (rbac.Action.VIEW_ANALYTICS, rbac.Action.VIEW_INVENTORY))
    client = client_for(user)
    summary = client.get(g_space_url("", makerspace))
    assert summary.status_code == 200 and summary.data["can_manage"] is False
    assert client.get(g_space_url("-embed", makerspace, "sw-inv")).status_code == 200
    for method, name, _args in G_MANAGER_ROUTES:
        assert getattr(client, method)(g_space_url(name, makerspace), {}, format="json").status_code == 403


@pytest.mark.parametrize("method,name,args", G_SPACE_ROUTES)
def test_the_platform_grafana_is_superadmin_only(method, name, args):
    makerspace = space()
    configure(None)
    response = getattr(client_for(manager(makerspace)), method)(g_platform_url(name, *args), {}, format="json")
    assert response.status_code == 403


def test_the_superadmin_reads_the_platform_grafana_without_a_module_switch():
    configure(None)
    response = client_for(superadmin()).get(g_platform_url(""))
    assert response.status_code == 200 and response.data["can_manage"] is True


def test_provider_hides_the_other_tool():
    makerspace = space()
    configure(makerspace, provider="metabase")
    client = client_for(manager(makerspace))
    grafana = client.get(g_space_url("", makerspace)).data
    assert grafana["configured"] is False and grafana["dashboards"] == []
    assert client.get(g_space_url("-embed", makerspace, "sw-inv")).data["code"] == "grafana_not_enabled"
    row = configure(makerspace, provider="grafana")
    row.metabase_url, row.dashboards = "https://mb.example.org", [{"id": 4, "title": "M"}]
    row.set_embed_secret("s" * 64)
    row.save()
    metabase = client.get(space_url("", makerspace)).data
    assert metabase["provider"] == "grafana" and metabase["configured"] is False
    assert client.get(space_url("-embed", makerspace, 4)).data["code"] == "analytics_not_configured"
    configure(makerspace, provider="both")
    assert client.get(space_url("", makerspace)).data["configured"] is True
    assert client.get(g_space_url("", makerspace)).data["configured"] is True


def test_route_classes():
    assert {route_class(f"admin-makerspace-grafana{name}") for name in ("", "-embed", "-render")} == {DELEGABLE}
    for name in ("-connection", "-token", "-test", "-bundle"):
        assert route_class(f"admin-makerspace-grafana{name}") == MEMBERSHIP_ONLY
    for name in ("", "-connection", "-token", "-test", "-bundle", "-embed", "-render"):
        assert route_class(f"admin-platform-grafana{name}") == PLATFORM_ONLY
