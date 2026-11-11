"""Public association documents use approved production identities and host trust."""

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.makerspaces import hosting
from apps.makerspaces.models import Makerspace
from tests.device_helpers import make_native_app_registration
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db
ANDROID = "/.well-known/assetlinks.json"
APPLE = "/.well-known/apple-app-site-association"
APP = "org.spaceworks.association"
PREFIX = "TEAMID1234"
DIGESTS = ["ab" * 32, "cd" * 32]


@pytest.fixture(autouse=True)
def association_hosts(settings):
    settings.ALLOWED_HOSTS = ["*"]
    settings.PUBLIC_APP_BASE_URL = "https://app.example.test"
    settings.PLATFORM_STAFF_ORIGINS = ["https://second.example.test"]
    settings.PLATFORM_DOMAIN_SUFFIX = ""
    settings.INFRA_HOSTS = {"testserver", "app.example.test", "second.example.test", "api.example.test"}
    settings.SECURE_SSL_REDIRECT = False
    settings.DEVICE_ATTESTATION_APPS = {}
    hosting.invalidate()
    yield
    hosting.invalidate()


def approved_app(platform, **overrides):
    row = make_native_app_registration(platform=platform, app_id=APP, environment="production", **overrides)
    row.signing_identities = [PREFIX] if platform == "apple" else DIGESTS
    row.save(update_fields=["signing_identities"])
    return row


def domain(*, status="verified", archived=False):
    space = make_space("m1e-association-domain")
    Makerspace.objects.filter(pk=space.pk).update(
        frontend_domain="custom.example.test", frontend_domain_status=status,
        archived_at=timezone.now() if archived else None,
    )
    hosting.invalidate()
    return space


def get(path, host="app.example.test", **headers):
    return APIClient().get(path, HTTP_HOST=host, **headers)


@pytest.mark.parametrize("path,empty", [
    (ANDROID, []), (APPLE, {"applinks": {"apps": [], "details": []}, "webcredentials": {"apps": []}}),
])
def test_empty_associations_are_public_json_with_short_cache_and_no_redirect(path, empty):
    result = get(path, HTTP_AUTHORIZATION="Bearer intentionally-invalid")
    assert result.status_code == 200
    assert result["Content-Type"] == "application/json"
    assert result["Cache-Control"] == "public, max-age=300"
    assert "Location" not in result
    assert result.json() == empty


def test_android_document_publishes_all_distribution_fingerprints_and_no_ineligible_rows():
    approved_app("android")
    for app_id, status, environment, tenant in [
        ("org.bad.revoked", "revoked", "production", None),
        ("org.bad.pending", "pending", "production", None),
        ("org.bad.development", "approved", "development", None),
        ("org.bad.tenant", "approved", "production", make_space("m1e-android-tenant")),
    ]:
        row = make_native_app_registration(platform="android", app_id=app_id, status=status,
                                           environment=environment, makerspace=tenant)
        row.signing_identities = DIGESTS
        row.save()
    response = get(ANDROID)
    assert response.status_code == 200 and response["Content-Type"] == "application/json"
    assert response.json() == [{
        "relation": ["delegate_permission/common.handle_all_urls"],
        "target": {"namespace": "android_app", "package_name": APP,
                   "sha256_cert_fingerprints": [":".join(["AB"] * 32), ":".join(["CD"] * 32)]},
    }]


def test_apple_document_uses_app_id_prefix_bundle_and_excludes_every_ineligible_row():
    approved_app("apple")
    tenant = make_space("m1e-apple-tenant")
    for app_id, status, environment, space in [
        ("org.bad.revoked", "revoked", "production", None),
        ("org.bad.pending", "pending", "production", None),
        ("org.bad.development", "approved", "development", None),
        ("org.bad.tenant", "approved", "production", tenant),
    ]:
        row = make_native_app_registration(platform="apple", app_id=app_id, status=status,
                                           environment=environment, makerspace=space)
        row.signing_identities = [PREFIX]
        row.save()
    result = get(APPLE)
    assert result.status_code == 200 and result["Content-Type"] == "application/json"
    document = result.json()
    assert document["applinks"]["apps"] == []
    assert document["webcredentials"] == {"apps": [f"{PREFIX}.{APP}"]}
    [detail] = document["applinks"]["details"]
    assert detail["appIDs"] == [f"{PREFIX}.{APP}"]
    assert {"/": "/m/*/admin/*", "exclude": True} in detail["components"]
    assert {"/": "/control/*", "exclude": True} in detail["components"]
    assert detail["components"][-1] == {"/": "/*", "exclude": True}


@pytest.mark.parametrize("managed", [False, True])
@pytest.mark.parametrize("path", [ANDROID, APPLE])
@pytest.mark.parametrize("host", ["app.example.test", "second.example.test", "custom.example.test"])
def test_primary_frontend_hosts_and_verified_custom_domain_are_served(settings, managed, path, host):
    settings.PLATFORM_DOMAIN_SUFFIX = ".example.test" if managed else ""
    domain()
    assert get(path, host).status_code == 200


@pytest.mark.parametrize("managed", [False, True])
@pytest.mark.parametrize("path", [ANDROID, APPLE])
@pytest.mark.parametrize("state", ["unknown", "unverified", "archived"])
def test_untrusted_domains_are_refused_by_existing_host_gate(settings, managed, path, state):
    settings.PLATFORM_DOMAIN_SUFFIX = ".example.test" if managed else ""
    if state != "unknown":
        domain(status="pending" if state == "unverified" else "verified", archived=state == "archived")
    result = get(path, "custom.example.test")
    assert result.status_code == (400 if managed else 404)
    assert "Location" not in result


def test_shared_and_custom_apple_components_include_all_contract_destinations():
    approved_app("apple")
    domain()
    expected = {
        "/member", "/member/*", "/member/account", "/member/events/*/ticket",
        "/events/*", "/bookings/*", "/items/*",
    }
    for host, prefix in (("app.example.test", "/m/*"), ("custom.example.test", "")):
        components = get(APPLE, host).json()["applinks"]["details"][0]["components"]
        included = {entry["/"] for entry in components if not entry.get("exclude")}
        assert {prefix + path for path in expected} <= included


def test_serving_associations_does_not_trust_an_arbitrary_browser_origin(settings):
    settings.PLATFORM_DOMAIN_SUFFIX = ".example.test"
    result = get(ANDROID, HTTP_ORIGIN="https://attacker.example.test")
    assert result.status_code == 200
    assert "Access-Control-Allow-Origin" not in result
    assert get(ANDROID, "api.example.test").status_code == 404
