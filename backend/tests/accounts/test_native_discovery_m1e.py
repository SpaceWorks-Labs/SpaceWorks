"""Row-owned identities, inert tenant rows, and registration-owned version floors."""

from pathlib import Path

import pytest
from django.core.checks.registry import registry
from rest_framework.test import APIClient

from apps.accounts import checks
from apps.accounts.attestation import AttestationUnavailable, configured_app
from apps.accounts.mobile_readiness import mobile_readiness
from apps.accounts.models import NativeAppRegistration
from apps.backup import settings_policy
from tests.accounts.test_device_auth import CHALLENGE, configure_apple
from tests.accounts.test_native_config_m1a import CONFIG
from tests.device_helpers import make_native_app_registration
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db


def registration(platform="apple", **overrides):
    values = {
        "platform": platform, "app_id": "org.spaceworks.discovery", "environment": "production",
        "status": "approved", "verifier_config_key": "row-key",
        "signing_identities": ["TEAMID1234"] if platform == "apple" else ["ab" * 32],
    }
    values.update(overrides)
    return NativeAppRegistration.objects.create(**values)


def test_configured_app_prefers_stored_identity_over_conflicting_legacy_config(settings):
    row = configure_apple(settings)
    row.signing_identities = ["ROWID12345"]
    row.save(update_fields=["signing_identities"])
    assert configured_app("apple", row.verifier_config_key, "development") == "ROWID12345"
    settings.DEVICE_ATTESTATION_APPS = {}
    assert configured_app("apple", row.verifier_config_key, "development") == "ROWID12345"


def test_legacy_fallback_warns_with_each_eligible_row_and_disappears_after_edit(settings):
    first = configure_apple(settings)
    other = make_native_app_registration(app_id="org.spaceworks.other", environment="production")
    settings.DEVICE_ATTESTATION_APPS["apple"][other.app_id] = {
        "signing_identity": "OTHER12345", "environments": ["production"],
    }
    tenant = make_native_app_registration(
        app_id="org.spaceworks.tenant", makerspace=make_space("m1e-legacy-tenant"),
    )
    revoked = make_native_app_registration(app_id="org.spaceworks.revoked", status="revoked")
    assert configured_app("apple", first.verifier_config_key, "development") == "TEAMID1234"
    assert configured_app("apple", other.verifier_config_key, "production") == "OTHER12345"
    warnings = checks.check_legacy_native_identities(databases=["default"])
    assert len(warnings) == 1 and warnings[0].id == "accounts.W001"
    for row in (first, other):
        assert f"#{row.pk} {row.app_id} ({row.environment})" in warnings[0].msg
    for row in (tenant, revoked):
        assert row.app_id not in warnings[0].msg
    for row, prefix in ((first, "TEAMID1234"), (other, "OTHER12345")):
        row.signing_identities = [prefix]
        row.save(update_fields=["signing_identities"])
    assert checks.check_legacy_native_identities() == []


@pytest.mark.parametrize("bad_identity", [["invalid"], None, {"prefix": "TEAMID1234"}])
def test_nonempty_invalid_row_identity_does_not_fall_back_to_valid_env(settings, bad_identity):
    row = configure_apple(settings)
    # None is checked in memory because the JSON column itself is non-nullable.
    row.signing_identities = bad_identity
    with pytest.raises(AttestationUnavailable):
        configured_app("apple", row.verifier_config_key, "development", registration=row)


def test_legacy_environment_allowlist_still_applies(settings):
    row = configure_apple(settings)
    settings.DEVICE_ATTESTATION_APPS["apple"][row.app_id]["environments"] = ["production"]
    with pytest.raises(AttestationUnavailable):
        configured_app("apple", row.verifier_config_key, "development")


@pytest.mark.parametrize("platform,key", [("android", "android"), ("apple", "ios")])
def test_tenant_only_registration_is_inert_across_all_public_discovery(settings, platform, key):
    settings.ALLOWED_HOSTS = ["*"]
    settings.PUBLIC_APP_BASE_URL = "https://app.example.test"
    settings.PLATFORM_DOMAIN_SUFFIX = ""
    settings.SECURE_SSL_REDIRECT = False
    settings.DEVICE_ATTESTATION_APPS = {}
    row = registration(platform, makerspace=make_space("m1e-discovery-tenant"), min_supported_version="99.0")
    client = APIClient()
    assert client.get(CONFIG).data["native"]["min_app_version"] == {"android": None, "ios": None}
    assert mobile_readiness()["platforms"][key]["registrations"] == []
    android = client.get("/.well-known/assetlinks.json", HTTP_HOST="app.example.test")
    apple = client.get("/.well-known/apple-app-site-association", HTTP_HOST="app.example.test")
    assert android.status_code == apple.status_code == 200
    assert android.json() == []
    assert apple.json()["applinks"]["details"] == []
    assert apple.json()["webcredentials"]["apps"] == []
    rejected = client.post(CHALLENGE, {
        "platform": platform, "app_id": row.app_id, "environment": "production",
    }, format="json")
    assert rejected.status_code == 503
    with pytest.raises(AttestationUnavailable):
        configured_app(platform, row.verifier_config_key, "production", registration=row)


def test_config_version_floor_is_numeric_and_only_approved_global_production_rows_count():
    make_space("m1e-version-config")
    registration("android", app_id="org.floor.old", min_supported_version="2.9.99", status="revoked")
    registration("android", app_id="org.floor.new", min_supported_version="2.10.0")
    registration("apple", min_supported_version="1.4.0")
    for platform in ("android", "apple"):
        registration(platform, app_id="org.floor.dev", environment="development", min_supported_version="99.0")
        registration(platform, app_id="org.floor.revoked", status="revoked", min_supported_version="99.0")
        registration(platform, app_id="org.floor.pending", status="pending", min_supported_version="99.0")
        registration(platform, app_id="org.floor.empty", min_supported_version=None, status="pending")
        registration(platform, makerspace=make_space(f"m1e-floor-{platform}"), min_supported_version="99.0")
    response = APIClient().get(CONFIG)
    assert response.status_code == 200
    assert response.data["native"]["min_app_version"] == {"android": "2.10.0", "ios": "1.4.0"}
    NativeAppRegistration.objects.filter(makerspace__isnull=True, environment="production").update(status="revoked")
    assert APIClient().get(CONFIG).data["native"]["min_app_version"] == {"android": None, "ios": None}


def test_removed_min_version_env_settings_checks_and_backup_policy_are_absent(settings):
    for name in ("MOBILE_MIN_VERSION_ANDROID", "MOBILE_MIN_VERSION_IOS"):
        assert not hasattr(settings, name)
    assert not any(name.startswith("MOBILE_MIN_VERSION_") for name in dir(settings))
    registered = [check for check in registry.get_checks(include_deployment_checks=True)
                  if check.__module__ == checks.__name__]
    assert not any("min_version" in check.__name__ or "min_app_version" in check.__name__
                   for check in registered)
    assert not any(name.startswith("MOBILE_MIN_VERSION_") for name in settings_policy.ENV_SURFACE)
    assert not any(name.startswith("MOBILE_MIN_VERSION_") for name in settings_policy.POLICIES)
    backend = Path(__file__).resolve().parents[2]
    sources = (backend / "config/settings.py", *sorted((backend / "config").glob("settings_*.py")),
               backend / "apps/accounts/checks.py", backend / "apps/backup/settings_policy.py")
    for path in sources:
        assert "MOBILE_MIN_VERSION_" not in path.read_text(encoding="utf-8")
