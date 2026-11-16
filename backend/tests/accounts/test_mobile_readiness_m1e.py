import json

import pytest
from django.test import Client
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.mobile_readiness import mobile_readiness
from apps.accounts.models import User
from apps.accounts.models_attestation import PlatformAttestationSettings
from apps.accounts.models_login_methods import PlatformLoginMethods
from apps.accounts.models_social import PlatformSocialAuthSettings
from apps.audit.models import AuditLog
from apps.integrations.models_push import PlatformPushSettings
from tests.accounts.control_mfa_helpers import force_control_mfa_login
from tests.accounts.mobile_integration_helpers import APP, registration
from tests.module_helpers import disable_module
from tests.return_helpers import make_space, make_user

pytestmark = pytest.mark.django_db
URL = "/api/v1/admin/platform/mobile-readiness"
SECRET = "private-server-credential-never-in-readiness"


@pytest.fixture(autouse=True)
def readiness_settings(settings):
    settings.PUBLIC_APP_BASE_URL = "https://app.example.test"
    settings.DEVICE_ATTESTATION_APPS = {}
    settings.DEVICE_ATTESTATION_DEV_INSECURE = False
    settings.DEVICE_ANDROID_ATTESTATION_VERIFY_URL = ""
    settings.DEVICE_ANDROID_ATTESTATION_VERIFY_TOKEN = ""
    settings.DEVICE_APPLE_ATTESTATION_VERIFY_URL = ""
    settings.DEVICE_APPLE_ATTESTATION_VERIFY_TOKEN = ""
    PlatformLoginMethods.objects.update_or_create(pk=1, defaults={"social_enabled": False})


def platform(key="ios"):
    return mobile_readiness()["platforms"][key]


def test_in_process_login_and_optional_settings_flip_independently_per_registration():
    registration("apple")
    other = registration("apple", app_id="org.example.other", environment="development")
    report = platform()
    assert report["login_ready"]
    first, second = report["registrations"]
    assert not first["optional"]["push"]["ready"]
    assert not second["optional"]["push"]["ready"]
    push = PlatformPushSettings.objects.create(
        pk=1, apns_private_key=SECRET, apns_team_id="APNSTEAM00", apns_key_id="key-id", apns_topic=APP,
    )
    report = platform()
    rows = {row["hint"].split()[0]: row for row in report["registrations"]}
    assert rows[APP]["optional"]["push"]["ready"]
    assert not rows[other.app_id]["optional"]["push"]["ready"]
    assert report["login_ready"]
    assert rows[APP]["optional"]["associations"]["ready"]
    social = PlatformSocialAuthSettings.objects.create(
        pk=1, apple_private_key=SECRET, apple_team_id="SOCIALTEAM", apple_key_id="social-key",
    )
    assert platform()["apple_revocation_ready"]
    for field in ("apns_private_key", "apns_team_id", "apns_key_id", "apns_topic"):
        original = getattr(push, field)
        setattr(push, field, "")
        push.save()
        assert not platform()["push_ready"]
        setattr(push, field, original)
    for field in ("apple_private_key", "apple_team_id", "apple_key_id"):
        original = getattr(social, field)
        setattr(social, field, "")
        social.save()
        assert not platform()["apple_revocation_ready"]
        setattr(social, field, original)
    assert SECRET not in json.dumps(mobile_readiness())


def test_android_attestation_and_fcm_configuration_are_separate():
    registration()
    assert not platform("android")["login_ready"]
    PlatformAttestationSettings.objects.create(pk=1, play_integrity_service_account=SECRET)
    report = platform("android")
    assert report["login_ready"] and not report["push_ready"]
    PlatformPushSettings.objects.create(pk=1, fcm_service_account=SECRET)
    assert platform("android")["push_ready"]
    assert SECRET not in json.dumps(mobile_readiness())


def test_login_requires_mobile_and_each_enabled_native_provider_audience():
    registration("apple")
    space = make_space("readiness-module")
    disable_module(space, "mobile")
    assert not platform()["registrations"][0]["login"]["mobile"]["ready"]
    space.refresh_from_db()
    space.enabled_modules = [*space.enabled_modules, "mobile"]
    space.save()
    PlatformLoginMethods.objects.update_or_create(pk=1, defaults={
        "social_enabled": True, "google_enabled": True, "apple_enabled": True,
    })
    assert not platform()["login_ready"]
    social = PlatformSocialAuthSettings.objects.create(pk=1, google_ios_client_id="native-ios-id")
    checks = platform()["registrations"][0]["login"]
    assert checks["google"]["ready"] and not checks["apple"]["ready"]
    social.apple_native_app_ids = [APP]
    social.save()
    assert platform()["login_ready"]
    social.google_ios_client_id = ""
    social.save()
    assert not platform()["login_ready"]


def test_external_https_and_token_are_required_and_never_exposed(settings):
    registration()
    settings.DEVICE_ANDROID_ATTESTATION_VERIFY_TOKEN = SECRET
    settings.DEVICE_ANDROID_ATTESTATION_VERIFY_URL = "http://verifier.example.test"
    assert not platform("android")["login_ready"]
    settings.DEVICE_ANDROID_ATTESTATION_VERIFY_URL = "https://verifier.example.test"
    assert platform("android")["login_ready"]
    assert SECRET not in json.dumps(mobile_readiness())
    assert "verifier.example.test" not in json.dumps(mobile_readiness())
    settings.DEVICE_ANDROID_ATTESTATION_VERIFY_TOKEN = ""
    assert not platform("android")["login_ready"]


def test_development_insecure_never_counts_for_production(settings):
    settings.DEBUG = True
    settings.DEVICE_ATTESTATION_DEV_INSECURE = True
    registration()
    registration(environment="development")
    report = platform("android")
    assert not report["login_ready"]
    assert not next(row for row in report["registrations"] if row["production"])["login_ready"]
    development = next(row for row in report["registrations"] if not row["production"])
    assert development["login_ready"]
    assert not development["optional"]["associations"]["ready"]


def test_ineligible_registrations_are_absent_and_reports_have_no_write_side_effects():
    registration("apple", makerspace=make_space("readiness-tenant"))
    registration("apple", status="revoked")
    registration("apple", app_id="org.example.pending", status="pending")
    before = AuditLog.objects.count()
    assert platform()["registrations"] == []
    assert not platform()["login_ready"]
    assert AuditLog.objects.count() == before
    assert not PlatformAttestationSettings.objects.exists()
    assert not PlatformSocialAuthSettings.objects.exists()
    assert not PlatformPushSettings.objects.exists()


def test_api_superadmin_only_and_control_page_reuses_builder_without_read_audit():
    assert APIClient().get(URL).status_code == 401
    regular = make_user("readiness-member")
    client = APIClient()
    client.force_authenticate(regular)
    assert client.get(URL).status_code == 403
    root = make_user("readiness-root", is_staff=True, is_superuser=True, role=User.Role.SUPERADMIN)
    client.force_authenticate(root)
    registration("apple")
    before = AuditLog.objects.count()
    response = client.get(URL)
    assert response.status_code == 200 and response.data == mobile_readiness()
    assert response["Cache-Control"] == "no-store"
    control = Client()
    force_control_mfa_login(control, root)
    before = AuditLog.objects.count()
    page = control.get(reverse("admin:accounts_nativeappregistration_mobile_readiness"))
    assert page.status_code == 200
    assert page.context_data["platforms"] == response.data["platforms"]
    assert control.post(reverse("admin:accounts_nativeappregistration_mobile_readiness")).status_code == 405
    changelist = control.get(reverse("admin:accounts_nativeappregistration_changelist"))
    assert b"Mobile readiness" in changelist.content
    assert AuditLog.objects.count() == before


def test_android_google_audience_is_platform_specific_and_disabled_providers_do_not_block():
    registration()
    PlatformAttestationSettings.objects.create(pk=1, play_integrity_service_account=SECRET)
    PlatformLoginMethods.objects.update_or_create(pk=1, defaults={
        "social_enabled": True, "google_enabled": True, "apple_enabled": False,
    })
    social = PlatformSocialAuthSettings.objects.create(pk=1, google_ios_client_id="ios-only")
    assert not platform("android")["registrations"][0]["login"]["google"]["ready"]
    social.google_android_client_id = "android-client"
    social.save()
    assert platform("android")["login_ready"]
    social.google_android_client_id = ""
    social.save()
    PlatformLoginMethods.objects.filter(pk=1).update(google_enabled=False)
    assert platform("android")["login_ready"]


def test_enabled_oidc_and_valid_registration_identity_are_login_requirements():
    from apps.accounts.models_oidc import OidcProvider

    row = registration("apple")
    PlatformLoginMethods.objects.update_or_create(pk=1, defaults={
        "social_enabled": True, "google_enabled": False, "apple_enabled": False,
    })
    oidc = OidcProvider.objects.create(slug="campus", display_name="Campus",
        issuer="https://id.example.test", jwks_url="https://id.example.test/jwks", client_id="")
    assert not platform()["registrations"][0]["login"]["oidc:campus"]["ready"]
    oidc.client_id = "native-public-client"
    oidc.save()
    assert platform()["login_ready"]
    row.signing_identities = ["invalid-prefix"]
    row.save()
    report = platform()
    assert not report["login_ready"]
    assert not report["registrations"][0]["login"]["registration"]["ready"]
    assert not report["associations_ready"]
