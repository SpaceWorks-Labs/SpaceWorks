"""Every mounted API pattern has an account classification or a deliberate exemption."""
from types import ModuleType

import pytest
from django.http import HttpResponse
from django.test import override_settings
from django.urls import get_resolver, include, path, re_path, URLPattern, URLResolver

from apps.accounts.checks import check_delegated_routes
from apps.accounts.delegated_routes import route_class
from apps.accounts.route_exemptions import PROVIDER_ONLY_ROUTES, route_exemption
from apps.accounts.surface_policy import _platform_route
from apps.admin_api.permissions import IsActiveSuperAdmin


def patterns(items, prefix=""):
    # Independent walker: a regression in the production prefix filter cannot make
    # this coverage assertion silently skip non-admin downloads/stations again.
    for item in items:
        route = prefix + str(item.pattern).removeprefix("^").removesuffix("$")
        if isinstance(item, URLResolver):
            yield from patterns(item.url_patterns, route)
        elif isinstance(item, URLPattern):
            yield route, item


def test_every_url_pattern_is_classified_or_deliberately_exempt():
    rows = list(patterns(get_resolver().url_patterns))
    assert rows
    missing = [(route, item.name) for route, item in rows
               if route_class(item.name) is None and route_exemption(route, item.name) is None]
    assert missing == []
    assert check_delegated_routes() == []


def test_every_platform_api_remains_reachable_by_platform_accounts():
    missing = []
    for route, item in patterns(get_resolver().url_patterns):
        if not route.startswith("api/v1/"):
            continue
        cls = getattr(item.callback, "cls", None)
        platform_permission = IsActiveSuperAdmin in getattr(cls, "permission_classes", ())
        if (platform_permission or route.startswith("api/v1/admin/platform/")) and not _platform_route(item.name):
            missing.append((route, item.name))
    assert missing == []


@pytest.mark.parametrize("prefix", ["api/v1/kiosk-stations/", "api/v1/downloads/", "api/v1/admin/"])
@pytest.mark.parametrize("name", ["future-staff-operation", None])
def test_unknown_and_unnamed_routes_fail_even_outside_admin(prefix, name):
    urls = ModuleType("stage4_urls")
    urls.urlpatterns = [path(prefix, include([re_path(r"^future/$", lambda request: HttpResponse(), name=name)]))]
    with override_settings(ROOT_URLCONF=urls):
        errors = check_delegated_routes()
    assert [error.id for error in errors] == ["accounts.E001"]


def test_media_exemption_does_not_grant_any_account_surface():
    assert "notification-media" in PROVIDER_ONLY_ROUTES
    assert route_class("notification-media") is None
    assert not _platform_route("notification-media")
    assert route_exemption("api/v1/integrations/notification-media/<str:token>.pdf", "notification-media") == "provider-only"


@pytest.mark.parametrize("name", ["payment-document-download", "kiosk-station-operator-lease",
    "kiosk-station-work-package", "kiosk-station-evidence-prepare", "kiosk-station-command-online"])
def test_non_admin_staff_transports_have_explicit_classification(name):
    assert route_class(name) == "delegable"
