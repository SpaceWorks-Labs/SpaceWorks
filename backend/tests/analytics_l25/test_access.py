"""L25 (#163B): module switch, view_analytics gating, Space-Manager-only credentials and the
superadmin-only platform connection."""

import pytest

from apps.accounts import rbac
from apps.accounts.delegated_routes import DELEGABLE, MEMBERSHIP_ONLY, PLATFORM_ONLY, route_class
from apps.accounts.rbac_actions import ORGANIZATION_GRANTABLE_ACTIONS, ROLE_GRANTABLE_ACTIONS, expand_implied_actions
from apps.analytics.models import AnalyticsConnection
from apps.makerspaces.module_registry import BY_KEY, default_enabled_module_keys

from .helpers import (
    PLATFORM_ROUTES, SPACE_ROUTES, client_for, inventory_manager, manager, plain_member, platform_url,
    space, space_url, superadmin,
)

pytestmark = pytest.mark.django_db


def test_the_module_is_registered_off_by_default_in_the_reports_group():
    definition = BY_KEY["analytics"]
    assert (definition.group, definition.default_enabled, definition.is_core) == ("reports", False, False)
    assert "analytics" not in default_enabled_module_keys()


def test_view_analytics_is_a_grantable_action_implied_by_manage_makerspace():
    assert rbac.Action.VIEW_ANALYTICS == "view_analytics"
    assert rbac.Action.VIEW_ANALYTICS in ROLE_GRANTABLE_ACTIONS
    assert rbac.Action.VIEW_ANALYTICS in ORGANIZATION_GRANTABLE_ACTIONS
    assert rbac.Action.VIEW_ANALYTICS in expand_implied_actions({rbac.Action.MANAGE_MAKERSPACE})


@pytest.mark.parametrize("method,name,args", SPACE_ROUTES)
def test_module_off_answers_404_on_every_space_route(method, name, args):
    makerspace = space(analytics=False)
    response = getattr(client_for(manager(makerspace)), method)(space_url(name, makerspace, *args), {}, format="json")
    assert response.status_code == 404
    assert not AnalyticsConnection.objects.filter(makerspace=makerspace).exists()


@pytest.mark.parametrize("method,name,args", SPACE_ROUTES)
def test_module_off_is_404_for_the_superadmin_too(method, name, args):
    makerspace = space(analytics=False)
    response = getattr(client_for(superadmin()), method)(space_url(name, makerspace, *args), {}, format="json")
    assert response.status_code == 404


def test_space_manager_and_superadmin_read_the_summary():
    makerspace = space()
    for user in (manager(makerspace), superadmin()):
        response = client_for(user).get(space_url("", makerspace))
        assert response.status_code == 200, response.data
        assert response.data["can_manage"] is True
        assert response.data["views_version"] >= 1


@pytest.mark.parametrize("make", [inventory_manager, plain_member])
def test_staff_without_view_analytics_are_refused(make):
    makerspace = space()
    client = client_for(make(makerspace))
    assert client.get(space_url("", makerspace)).status_code == 403
    assert client.get(space_url("-embed", makerspace, 7)).status_code == 403


def test_a_stranger_gets_404_not_403():
    makerspace, other = space(), space()
    response = client_for(manager(other)).get(space_url("", makerspace))
    assert response.status_code == 404


def test_view_analytics_alone_does_not_manage_credentials(monkeypatch):
    makerspace = space()
    user = inventory_manager(makerspace)
    monkeypatch.setattr(rbac, "can", lambda actor, action, makerspace_id=None:
                        action == rbac.Action.VIEW_ANALYTICS or action == rbac.Action.VIEW_INVENTORY)
    client = client_for(user)
    assert client.get(space_url("", makerspace)).status_code == 200
    assert client.get(space_url("", makerspace)).data["can_manage"] is False
    for method, name in (("get", "-connection"), ("patch", "-connection"), ("post", "-login"),
                         ("post", "-login-rotate"), ("delete", "-login")):
        assert getattr(client, method)(space_url(name, makerspace), {}, format="json").status_code == 403


@pytest.mark.parametrize("method,name,args", PLATFORM_ROUTES)
def test_the_platform_connection_is_superadmin_only(method, name, args):
    makerspace = space()
    response = getattr(client_for(manager(makerspace)), method)(platform_url(name, *args), {}, format="json")
    assert response.status_code == 403


def test_the_superadmin_reads_the_platform_summary_without_a_module_switch():
    response = client_for(superadmin()).get(platform_url(""))
    assert response.status_code == 200
    assert response.data["can_manage"] is True


def test_route_classes():
    assert route_class("admin-makerspace-analytics") == DELEGABLE
    assert route_class("admin-makerspace-analytics-embed") == DELEGABLE
    for name in ("connection", "login", "login-rotate"):
        assert route_class(f"admin-makerspace-analytics-{name}") == MEMBERSHIP_ONLY
    for name in ("", "-connection", "-login", "-login-rotate", "-embed"):
        assert route_class(f"admin-platform-analytics{name}") == PLATFORM_ONLY


def test_routes_do_not_collide_with_the_platform_report_route():
    from django.urls import resolve
    assert resolve(platform_url("-connection")).url_name == "admin-platform-analytics-connection"
    assert resolve(platform_url("-login")).url_name == "admin-platform-analytics-login"
