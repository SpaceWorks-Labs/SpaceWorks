"""Decision 263 addendum (owner, 2026-11-11): web telemetry is limited to its own scope.

A space's public bootstrap carries that space's provider identifiers only: never another
space's, never the platform's (no fallback). The platform's identifiers appear only in the
platform's public config. With the analytics module off a space projects the inert defaults.
Staff settings routes stay pinned to the caller's own space; the platform row is superadmin-only.
"""

import json

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.analytics.models import AnalyticsConnection, PlatformAnalyticsConnection
from apps.makerspaces.telemetry_defaults import defaults
from tests.analytics_l25.helpers import client_for, manager, space, superadmin

pytestmark = pytest.mark.django_db


def _config(tag):
    """A valid public config whose every identifier carries ``tag``."""
    config = defaults()
    config["pageview"] = {"provider": "ga4", "site_id": f"G-{tag}PAGE", "endpoint": ""}
    config["replay"] = {"provider": "clarity", "site_id": f"{tag}replay", "endpoint": ""}
    config["firebase"].update(api_key=f"{tag}apikey", project_id=f"{tag.lower()}-project",
                              app_id=f"1:{tag}:web", measurement_id=f"G-{tag}FB")
    return config


def _identifiers(tag):
    return (f"G-{tag}PAGE", f"{tag}replay", f"{tag}apikey", f"{tag.lower()}-project", f"G-{tag}FB")


def _configure_space(makerspace, tag):
    AnalyticsConnection.objects.update_or_create(makerspace=makerspace, defaults={"telemetry_config": _config(tag)})


def _configure_platform(tag):
    row = PlatformAnalyticsConnection.load()
    row.telemetry_config = _config(tag)
    row.save(update_fields=["telemetry_config", "updated_at"])


def _bootstrap(makerspace):
    response = APIClient().get(reverse("tenant-bootstrap"), {"slug": makerspace.slug})
    assert response.status_code == 200, response.content
    return response.json()


def _public_config():
    response = APIClient().get(reverse("public-config"))
    assert response.status_code == 200, response.content
    return response.json()


def _assert_absent(body, tags):
    text = json.dumps(body)
    for tag in tags:
        for identifier in _identifiers(tag):
            assert identifier not in text, f"{identifier} leaked"


@pytest.fixture
def scenario():
    first, second = space("tela"), space("telb")
    _configure_space(first, "AAA")
    _configure_space(second, "BBB")
    _configure_platform("PPP")
    return first, second


def test_each_space_bootstrap_carries_only_its_own_identifiers(scenario):
    first, second = scenario
    body = _bootstrap(first)
    assert body["telemetry"] == _config("AAA")
    _assert_absent(body, ("BBB", "PPP"))
    body = _bootstrap(second)
    assert body["telemetry"] == _config("BBB")
    _assert_absent(body, ("AAA", "PPP"))


def test_platform_config_is_only_in_the_platform_projection(scenario):
    body = _public_config()
    assert body["platform_telemetry"] == _config("PPP")
    _assert_absent(body, ("AAA", "BBB"))
    assert "telemetry" not in body


def test_unconfigured_space_never_falls_back_to_the_platform(scenario):
    blank = space("telc")
    body = _bootstrap(blank)
    assert body["telemetry"] == defaults()
    _assert_absent(body, ("AAA", "BBB", "PPP"))


def test_module_off_projects_inert_defaults_and_keeps_the_row(scenario):
    first, _second = scenario
    first.enabled_modules = sorted(set(first.enabled_modules or []) - {"analytics"})
    first.save(update_fields=["enabled_modules"])
    body = _bootstrap(first)
    assert body["telemetry"] == defaults()
    assert body["telemetry_legacy_allowed"] is False
    _assert_absent(body, ("AAA", "BBB", "PPP"))
    # The configuration is retained and returns when the module is switched back on.
    assert AnalyticsConnection.objects.get(makerspace=first).telemetry_config == _config("AAA")
    first.enabled_modules = sorted({*first.enabled_modules, "analytics"})
    first.save(update_fields=["enabled_modules"])
    assert _bootstrap(first)["telemetry"] == _config("AAA")


def test_space_manager_cannot_read_or_write_another_space_or_the_platform(scenario):
    first, second = scenario
    client = client_for(manager(first))
    foreign = reverse("admin-makerspace-telemetry", kwargs={"makerspace_id": second.pk})
    assert client.get(foreign).status_code == 404
    assert client.patch(foreign, {"config": defaults()}, format="json").status_code == 404
    assert AnalyticsConnection.objects.get(makerspace=second).telemetry_config == _config("BBB")
    platform = reverse("admin-platform-telemetry")
    assert client.get(platform).status_code == 403
    assert client.patch(platform, {"config": defaults()}, format="json").status_code == 403
    assert PlatformAnalyticsConnection.load().telemetry_config == _config("PPP")
    own = client.get(reverse("admin-makerspace-telemetry", kwargs={"makerspace_id": first.pk}))
    assert own.status_code == 200
    _assert_absent(own.data, ("BBB", "PPP"))


def test_superadmin_platform_write_never_touches_a_space(scenario):
    first, second = scenario
    route = reverse("admin-platform-telemetry")
    response = client_for(superadmin()).patch(route, {"config": defaults()}, format="json")
    assert response.status_code == 200, response.data
    assert _bootstrap(first)["telemetry"] == _config("AAA")
    assert _bootstrap(second)["telemetry"] == _config("BBB")
    assert _public_config()["platform_telemetry"] == defaults()
