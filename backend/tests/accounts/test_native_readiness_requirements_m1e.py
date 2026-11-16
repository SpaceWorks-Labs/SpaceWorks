"""Each readiness input changes its own check; optional inputs stay independent."""

import pytest
from cryptography.fernet import Fernet

from apps.accounts.mobile_readiness import mobile_readiness, registration_readiness
from apps.accounts.models import PlatformLoginMethods
from apps.accounts.models_attestation import PlatformAttestationSettings
from apps.accounts.models_social import PlatformSocialAuthSettings
from apps.integrations.models_push import PlatformPushSettings
from apps.makerspaces import hosting
from tests.accounts.oidc_browser_helpers import make_provider
from tests.device_helpers import make_native_app_registration
from tests.module_helpers import disable_module
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db
APP = "org.spaceworks.readiness"


@pytest.fixture(autouse=True)
def readiness_environment(settings):
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode()
    settings.PUBLIC_APP_BASE_URL = "https://app.example.test"
    settings.PLATFORM_STAFF_ORIGINS = []
    settings.PLATFORM_DOMAIN_SUFFIX = ""
    settings.DEVICE_ATTESTATION_APPS = {}
    settings.DEVICE_ATTESTATION_DEV_INSECURE = False
    for platform in ("APPLE", "ANDROID"):
        setattr(settings, f"DEVICE_{platform}_ATTESTATION_VERIFY_URL", "")
        setattr(settings, f"DEVICE_{platform}_ATTESTATION_VERIFY_TOKEN", "")
    PlatformLoginMethods.objects.update_or_create(pk=1, defaults={"social_enabled": False})
    hosting.invalidate()
    yield
    hosting.invalidate()


def registration(platform="apple", **overrides):
    options = {"app_id": APP, "platform": platform, "environment": "production", **overrides}
    row = make_native_app_registration(**options)
    row.signing_identities = ["TEAMID1234"] if platform == "apple" else ["ab" * 32, "cd" * 32]
    row.save(update_fields=["signing_identities"])
    return row


def report(platform="ios"):
    return mobile_readiness()["platforms"][platform]


def checks(platform="ios"):
    return report(platform)["registrations"][0]


@pytest.mark.parametrize("failure", ["pending", "revoked", "tenant", "invalid-signers"])
def test_registration_check_fails_for_each_ineligible_identity(failure):
    row = registration()
    if failure in {"pending", "revoked"}:
        row.status = failure
    elif failure == "tenant":
        row.makerspace = make_space("m1e-readiness-tenant")
    else:
        row.signing_identities = ["bad-prefix"]
    row.save()
    result = registration_readiness(row, social=None, push=None, mobile_enabled=True, has_hosts=True)
    assert result["login"]["registration"]["ready"] is False
    assert result["login_ready"] is False
    if failure != "invalid-signers":
        assert report()["registrations"] == []


def test_apple_in_process_needs_prefix_and_no_private_credential():
    registration()
    assert checks()["login"]["attestation"]["ready"] is True
    assert report()["login_ready"] is True
    assert not PlatformAttestationSettings.objects.exists()
    assert not report()["push_ready"]
    assert not report()["apple_revocation_ready"]


def test_android_service_account_and_fcm_flip_separately():
    registration("android")
    assert not checks("android")["login"]["attestation"]["ready"]
    account = PlatformAttestationSettings.load()
    account.set_play_integrity_service_account('{"private_key":"attestation-secret"}')
    account.save()
    assert report("android")["login_ready"]
    assert not report("android")["push_ready"]
    push = PlatformPushSettings.load()
    push.set_fcm_service_account('{"private_key":"fcm-secret"}')
    push.save()
    assert report("android")["push_ready"]
    account.set_play_integrity_service_account("")
    account.save()
    assert not report("android")["login_ready"]
    assert report("android")["push_ready"]
    push.set_fcm_service_account("")
    push.save()
    assert not report("android")["push_ready"]


@pytest.mark.parametrize("url,token,ready", [
    ("", "", False), ("https://verify.example.test", "", False),
    ("", "private-token", False), ("http://verify.example.test", "private-token", False),
    ("https://", "private-token", False), ("https://verify.example.test", "private-token", True),
])
def test_external_attestation_requires_https_host_and_token(settings, url, token, ready):
    registration("android")
    settings.DEVICE_ANDROID_ATTESTATION_VERIFY_URL = url
    settings.DEVICE_ANDROID_ATTESTATION_VERIFY_TOKEN = token
    assert checks("android")["login"]["attestation"]["ready"] is ready
    assert report("android")["login_ready"] is ready


def test_invalid_explicit_apple_external_configuration_is_not_reported_as_in_process_ready(settings):
    registration()
    settings.DEVICE_APPLE_ATTESTATION_VERIFY_URL = "http://verify.example.test"
    settings.DEVICE_APPLE_ATTESTATION_VERIFY_TOKEN = "private-token"
    assert not checks()["login"]["attestation"]["ready"]
    settings.DEVICE_APPLE_ATTESTATION_VERIFY_URL = "https://verify.example.test"
    assert checks()["login"]["attestation"]["ready"]


def test_mobile_module_gate_flips_without_optional_settings_changing():
    registration()
    space = make_space("m1e-readiness-mobile")
    baseline = checks()
    disable_module(space, "mobile")
    assert not checks()["login"]["mobile"]["ready"]
    assert not report()["login_ready"]
    assert checks()["optional"] == baseline["optional"]
    space.refresh_from_db()
    space.enabled_modules = [*space.enabled_modules, "mobile"]
    space.save(update_fields=["enabled_modules"])
    assert checks()["login"]["mobile"]["ready"]
    assert report()["login_ready"]


@pytest.mark.parametrize("platform,key,field,wrong_field", [
    ("apple", "ios", "google_ios_client_id", "google_android_client_id"),
    ("android", "android", "google_android_client_id", "google_ios_client_id"),
])
def test_google_readiness_requires_the_matching_native_client_id(platform, key, field, wrong_field, settings):
    registration(platform)
    if platform == "android":
        settings.DEVICE_ANDROID_ATTESTATION_VERIFY_URL = "https://verify.example.test"
        settings.DEVICE_ANDROID_ATTESTATION_VERIFY_TOKEN = "token"
    PlatformLoginMethods.objects.filter(pk=1).update(social_enabled=True, google_enabled=True, apple_enabled=False)
    social = PlatformSocialAuthSettings.load()
    setattr(social, wrong_field, "opposite-platform-client")
    social.google_web_client_id = "web-client-does-not-count"
    social.save()
    assert not checks(key)["login"]["google"]["ready"]
    setattr(social, field, "matching-native-client")
    social.save()
    assert checks(key)["login"]["google"]["ready"]
    assert report(key)["login_ready"]
    setattr(social, field, "")
    social.save()
    PlatformLoginMethods.objects.filter(pk=1).update(google_enabled=False)
    assert "google" not in checks(key)["login"]
    assert report(key)["login_ready"]


def test_apple_native_allowlist_and_social_master_switch_flip_login_readiness():
    registration()
    PlatformLoginMethods.objects.filter(pk=1).update(social_enabled=True, google_enabled=False, apple_enabled=True)
    social = PlatformSocialAuthSettings.load()
    social.apple_service_id = APP  # A web service audience does not satisfy native login.
    social.apple_native_app_ids = ["org.other.app"]
    social.save()
    assert not checks()["login"]["apple"]["ready"]
    social.apple_native_app_ids = [APP]
    social.save()
    assert report()["login_ready"]
    social.apple_native_app_ids = []
    social.save()
    PlatformLoginMethods.objects.filter(pk=1).update(social_enabled=False)
    assert "apple" not in checks()["login"]
    assert report()["login_ready"]


@pytest.mark.parametrize("field", ["client_id", "issuer", "jwks_url"])
def test_every_enabled_oidc_configuration_input_flips_the_provider_check(field):
    registration()
    PlatformLoginMethods.objects.filter(pk=1).update(social_enabled=True, google_enabled=False, apple_enabled=False)
    provider = make_provider()
    assert report()["login_ready"]
    original = getattr(provider, field)
    setattr(provider, field, "")
    provider.save()
    assert not checks()["login"]["oidc:campus"]["ready"]
    assert not report()["login_ready"]
    setattr(provider, field, original)
    provider.save()
    assert report()["login_ready"]
    provider.is_enabled = False
    provider.save()
    assert "oidc:campus" not in checks()["login"]


@pytest.mark.parametrize("debug", [False, True])
def test_development_bypass_cannot_make_production_or_a_development_only_platform_ready(settings, debug):
    settings.DEBUG = debug
    settings.DEVICE_ATTESTATION_DEV_INSECURE = True
    registration("android", environment="development")
    assert checks("android")["login_ready"] is debug
    assert not checks("android")["optional"]["associations"]["ready"]
    assert not report("android")["login_ready"]  # No production registration.
    registration("android")
    production = next(row for row in report("android")["registrations"] if row["production"])
    assert not production["login"]["attestation"]["ready"]
    assert not production["login_ready"]
    assert not report("android")["login_ready"]


def test_platform_rollup_uses_production_and_keeps_unready_development_separate():
    registration()
    development = registration(environment="development")
    development.signing_identities = ["bad-prefix"]
    development.save(update_fields=["signing_identities"])
    result = report()
    assert result["login_ready"]
    assert result["associations_ready"]
    assert not next(row for row in result["registrations"] if not row["production"])["login_ready"]
