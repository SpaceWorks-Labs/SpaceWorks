from pathlib import Path

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.integrations.mobile_link_contract import association_patterns, is_supported_link
from apps.makerspaces import hosting
from apps.makerspaces.models import Makerspace
from tests.accounts.mobile_integration_helpers import APP, PREFIX, registration
from tests.accounts.test_native_proxy_links_m1e import publishing_lines
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db
ANDROID = "/.well-known/assetlinks.json"
APPLE = "/.well-known/apple-app-site-association"


@pytest.fixture(autouse=True)
def hosts(settings):
    settings.ALLOWED_HOSTS = ["*"]
    settings.PUBLIC_APP_BASE_URL = "https://app.example.test"
    settings.PLATFORM_STAFF_ORIGINS = ["https://second.example.test"]
    settings.PLATFORM_DOMAIN_SUFFIX = ""
    settings.INFRA_HOSTS = {"app.example.test", "second.example.test", "api.example.test"}
    settings.ENABLE_HTTPS = False
    settings.SECURE_SSL_REDIRECT = False
    hosting.invalidate()


def get(url, host="app.example.test", **headers):
    return APIClient().get(url, HTTP_HOST=host, **headers)


def custom_domain(*, status="verified", archived=False):
    space = make_space("association-domain")
    Makerspace.objects.filter(pk=space.pk).update(
        frontend_domain="custom.example.test", frontend_domain_status=status,
        archived_at=timezone.now() if archived else None,
    )
    hosting.invalidate()
    return space


def test_empty_documents_are_valid_json_without_redirects_or_authentication():
    for url, empty in ((ANDROID, []), (APPLE, {"applinks": {"apps": [], "details": []},
                                             "webcredentials": {"apps": []}})):
        response = get(url, HTTP_AUTHORIZATION="Bearer invalid-token")
        assert response.status_code == 200
        assert response["Content-Type"] == "application/json"
        assert response["Cache-Control"] == "public, max-age=300"
        assert "Location" not in response
        assert response.json() == empty


def test_only_approved_global_production_registrations_are_published():
    registration()
    registration("apple")
    registration(app_id="org.example.revoked", status="revoked")
    registration(app_id="org.example.pending", status="pending")
    registration(environment="development")
    registration(makerspace=make_space("association-tenant"))
    android = get(ANDROID).json()
    assert len(android) == 1
    assert android[0]["relation"] == ["delegate_permission/common.handle_all_urls"]
    target = android[0]["target"]
    assert target["package_name"] == APP
    assert len(target["sha256_cert_fingerprints"]) == 2
    assert target["sha256_cert_fingerprints"][0] == ":".join(["AB"] * 32)
    apple = get(APPLE).json()
    assert apple["webcredentials"]["apps"] == [f"{PREFIX}.{APP}"]
    assert apple["applinks"]["details"][0]["appIDs"] == [f"{PREFIX}.{APP}"]


@pytest.mark.parametrize("host", ["app.example.test", "second.example.test", "custom.example.test"])
def test_primary_and_verified_domain_hosts_are_served(host):
    custom_domain()
    assert get(ANDROID, host).status_code == 200
    assert get(APPLE, host).status_code == 200


@pytest.mark.parametrize("managed", [False, True])
@pytest.mark.parametrize("state", ["unknown", "unverified", "archived"])
def test_untrusted_domain_hosts_keep_managed_400_and_view_404(settings, managed, state):
    settings.PLATFORM_DOMAIN_SUFFIX = ".example.test" if managed else ""
    if state != "unknown":
        custom_domain(status="pending" if state == "unverified" else "verified", archived=state == "archived")
    for url in (ANDROID, APPLE):
        assert get(url, "custom.example.test").status_code == (400 if managed else 404)


def test_explicit_primary_self_host_ip_is_served(settings):
    settings.PUBLIC_APP_BASE_URL = "http://127.0.0.1:5000"
    assert get(ANDROID, "127.0.0.1:5000").status_code == 200


def test_infrastructure_host_is_not_a_public_application_host(settings):
    settings.PLATFORM_DOMAIN_SUFFIX = ".example.test"
    assert get(ANDROID, "api.example.test").status_code == 404


def test_apple_components_use_existing_contract_for_each_host_kind():
    registration("apple")
    custom_domain()
    for host, position in (("app.example.test", 0), ("custom.example.test", 1)):
        components = get(APPLE, host).json()["applinks"]["details"][0]["components"]
        included = {entry["/"] for entry in components if not entry.get("exclude")}
        assert {patterns[position] for patterns in association_patterns()} <= included
        excluded = {entry["/"] for entry in components if entry.get("exclude")}
        assert "/control/*" in excluded and "/m/*/admin/*" in excluded
        assert components[-1] == {"/": "/*", "exclude": True}
    assert is_supported_link("/m/space/member/events/123/ticket")
    assert is_supported_link("/items/12")
    assert not is_supported_link("/m/space/admin/inventory")


def test_association_request_does_not_grant_unregistered_origin_cors_trust():
    response = get(ANDROID, HTTP_ORIGIN="https://untrusted.example.test")
    assert response.status_code == 200
    assert "Access-Control-Allow-Origin" not in response


def test_association_proxies_are_exact_and_never_reach_control_or_tunnel_snippets():
    root = Path(__file__).resolve().parents[3]
    for relative in ("frontend/nginx.conf", "deploy/nginx.api-only.conf"):
        config = (root / relative).read_text()
        for url in (ANDROID, APPLE):
            assert f"location = {url} {{" in config
        assert "location /.well-known/" not in config
    for relative in ("deploy/Caddyfile", "deploy/Caddyfile.saas", "deploy/Caddyfile.saas-install"):
        config = (root / relative).read_text()
        for url in (ANDROID, APPLE):
            assert f"handle {url} {{" in config
        # `not path` exclusion lists (profile-card crawler) reserve the prefix; they publish nothing.
        assert "/.well-known/*" not in publishing_lines(config)
    for config in [*(root / "deploy").glob("control-plane-*.caddy"),
                   *(root / "deploy").glob("control-tunnel-*.caddy")]:
        assert "/.well-known/" not in config.read_text()
