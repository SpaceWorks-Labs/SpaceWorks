"""Optional readiness, per-bundle APNs checks, access control and recursive secrecy."""

import json
from unittest.mock import Mock

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.mobile_readiness import mobile_readiness
from apps.accounts.models import User
from apps.accounts.models_attestation import PlatformAttestationSettings
from apps.accounts.models_social import PlatformSocialAuthSettings
from apps.audit.models import AuditLog
from apps.integrations.models_push import PlatformPushSettings
from apps.makerspaces import hosting
from apps.makerspaces.models import Makerspace
from tests.accounts.control_mfa_helpers import force_control_mfa_login
from tests.accounts.test_native_readiness_requirements_m1e import (
    APP, checks, readiness_environment, registration, report,
)
from tests.return_helpers import make_space, make_user

pytestmark = pytest.mark.django_db
URL = "/api/v1/admin/platform/mobile-readiness"


@pytest.mark.parametrize("missing", ["apns_private_key", "apns_team_id", "apns_key_id", "apns_topic"])
def test_each_apns_requirement_flips_push_without_affecting_login(missing):
    registration()
    push = PlatformPushSettings.load()
    push.set_apns_private_key("apns-private-test-key")
    push.apns_team_id, push.apns_key_id, push.apns_topic = "APNSTEAM12", "APNSKEY123", APP
    push.save()
    assert report()["push_ready"] and report()["login_ready"]
    original = getattr(push, missing)
    setattr(push, missing, "")
    push.save()
    assert not checks()["optional"]["push"]["ready"]
    assert not report()["push_ready"]
    assert report()["login_ready"]
    setattr(push, missing, original)
    push.save()
    assert report()["push_ready"]


def test_apns_topic_is_checked_against_each_registration_and_aggregated():
    registration()
    other = registration(app_id="org.spaceworks.second", environment="development")
    push = PlatformPushSettings.load()
    push.set_apns_private_key("apns-private-test-key")
    push.apns_team_id, push.apns_key_id, push.apns_topic = "APNSTEAM12", "APNSKEY123", APP
    push.save()
    for topic in (APP, other.app_id, "org.spaceworks.unregistered"):
        push.apns_topic = topic
        push.save()
        result = report()
        rows = {row["hint"].split()[0]: row for row in result["registrations"]}
        for bundle in (APP, other.app_id):
            assert rows[bundle]["optional"]["push"]["ready"] is (bundle == topic)
        assert result["push_ready"] is (topic == APP)
        assert result["login_ready"]


@pytest.mark.parametrize("missing", ["apple_team_id", "apple_key_id", "apple_private_key"])
def test_each_apple_revocation_requirement_flips_only_its_optional_check(missing):
    registration()
    social = PlatformSocialAuthSettings.load()
    social.apple_team_id, social.apple_key_id = "SOCIALTEAM", "SOCIALKEY1"
    social.set_apple_private_key("apple-revocation-private-test-key")
    social.save()
    assert report()["apple_revocation_ready"]
    original = getattr(social, missing)
    setattr(social, missing, "")
    social.save()
    assert not checks()["optional"]["apple_revocation"]["ready"]
    assert report()["login_ready"]
    setattr(social, missing, original)
    social.save()
    assert report()["apple_revocation_ready"]


def test_association_optional_check_tracks_eligible_hosts_and_production(settings):
    registration()
    settings.PUBLIC_APP_BASE_URL = ""
    assert not report()["associations_ready"]
    settings.PUBLIC_APP_BASE_URL = "https://app.example.test"
    assert report()["associations_ready"]
    settings.PUBLIC_APP_BASE_URL = ""
    space = make_space("m1e-readiness-domain")
    Makerspace.objects.filter(pk=space.pk).update(
        frontend_domain="custom.example.test", frontend_domain_status="pending",
    )
    hosting.invalidate()
    assert not report()["associations_ready"]
    Makerspace.objects.filter(pk=space.pk).update(frontend_domain_status="verified")
    hosting.invalidate()
    assert report()["associations_ready"]
    Makerspace.objects.filter(pk=space.pk).update(archived_at=timezone.now())
    hosting.invalidate()
    assert not report()["associations_ready"]
    assert report()["login_ready"]


@pytest.mark.parametrize("actor,expected", [
    ("anonymous", 401), ("member", 403), ("staff", 403),
    ("inactive-superuser", 403), ("suspended-superuser", 403),
    ("superuser", 200), ("superadmin-role", 200),
])
def test_readiness_api_requires_an_active_superadmin(actor, expected):
    client = APIClient()
    if actor != "anonymous":
        options = {"is_staff": actor != "member"}
        if "superuser" in actor:
            options["is_superuser"] = True
        if actor == "inactive-superuser":
            options["is_active"] = False
        if actor == "suspended-superuser":
            options["access_status"] = User.AccessStatus.SUSPENDED
        if actor == "superadmin-role":
            options["role"] = User.Role.SUPERADMIN
        client.force_authenticate(make_user("m1e-readiness-actor", **options))
    assert client.get(URL).status_code == expected


def test_api_and_control_page_share_the_builder_are_read_only_and_emit_no_read_audit(client):
    registration()
    root = User.objects.create_superuser(username="m1e-readiness-root", password="strong-root-password")
    api = APIClient()
    api.force_authenticate(root)
    force_control_mfa_login(client, root)
    before = AuditLog.objects.count()
    expected = mobile_readiness()
    response = api.get(URL)
    assert response.status_code == 200 and response.data == expected
    assert response["Cache-Control"] == "no-store"
    page_url = reverse("admin:accounts_nativeappregistration_mobile_readiness")
    page = client.get(page_url)
    assert page.status_code == 200
    assert page.context_data["platforms"] == expected["platforms"]
    assert "private" in page["Cache-Control"]
    assert "no-store" in page["Cache-Control"]
    assert api.post(URL, {}, format="json").status_code == 405
    assert client.post(page_url).status_code == 405
    assert AuditLog.objects.count() == before


def test_control_readiness_is_not_accessible_to_staff_or_anonymous_users(client):
    page_url = reverse("admin:accounts_nativeappregistration_mobile_readiness")
    assert client.get(page_url).status_code == 302
    staff = make_user("m1e-readiness-control-staff", is_staff=True)
    client.force_login(staff)
    assert client.get(page_url).status_code == 403


def assert_no_secret_anywhere(value, secrets):
    """Walk keys and leaves, including arbitrarily nested future report sections."""
    if isinstance(value, dict):
        for key, child in value.items():
            assert_no_secret_anywhere(key, secrets)
            assert_no_secret_anywhere(child, secrets)
    elif isinstance(value, list):
        for child in value:
            assert_no_secret_anywhere(child, secrets)
    elif isinstance(value, str):
        for secret in secrets:
            assert secret not in value
    else:
        assert isinstance(value, bool), f"Unexpected readiness value type: {type(value)}"


def test_no_raw_or_encrypted_credential_appears_anywhere_in_readiness_json(settings, monkeypatch):
    registration()
    registration("android")
    private = "-----BEGIN PRIVATE KEY-----\nm1e-sentinel-private-key-material\n-----END PRIVATE KEY-----"
    account_json = json.dumps({"type": "service_account", "client_email": "m1e-secret@example.test",
                               "private_key": private, "token": "m1e-service-account-token"})
    account = PlatformAttestationSettings.load()
    account.set_play_integrity_service_account(account_json)
    account.save()
    push = PlatformPushSettings.load()
    push.set_fcm_service_account(account_json)
    push.set_apns_private_key(private)
    push.apns_team_id, push.apns_key_id, push.apns_topic = "APNSTEAM12", "APNSKEY123", APP
    push.save()
    social = PlatformSocialAuthSettings.load()
    social.set_apple_private_key(private)
    social.set_github_client_secret("m1e-github-private-token")
    social.apple_team_id, social.apple_key_id = "SOCIALTEAM", "SOCIALKEY1"
    social.save()
    tokens = ["m1e-android-verifier-token", "m1e-apple-verifier-token"]
    for platform, token in zip(("ANDROID", "APPLE"), tokens):
        setattr(settings, f"DEVICE_{platform}_ATTESTATION_VERIFY_URL", "https://private-verifier.example.test")
        setattr(settings, f"DEVICE_{platform}_ATTESTATION_VERIFY_TOKEN", token)
    secrets = [account_json, private, "m1e-sentinel-private-key-material", "m1e-secret@example.test",
               "m1e-service-account-token", "m1e-github-private-token", *tokens,
               account.play_integrity_service_account, push.fcm_service_account,
               push.apns_private_key, social.apple_private_key, social.github_client_secret]
    # A read-only readiness report has no reason to decrypt or contact providers.
    forbidden = Mock(side_effect=AssertionError("Readiness must not decrypt or probe"))
    for model, getter in ((PlatformAttestationSettings, "get_play_integrity_service_account"),
                          (PlatformPushSettings, "get_fcm_service_account"),
                          (PlatformPushSettings, "get_apns_private_key"),
                          (PlatformSocialAuthSettings, "get_apple_private_key")):
        monkeypatch.setattr(model, getter, forbidden)
    monkeypatch.setattr("requests.post", forbidden)
    monkeypatch.setattr("requests.get", forbidden)
    root = User.objects.create_superuser(username="m1e-secret-reader", password="strong-root-password")
    client = APIClient()
    client.force_authenticate(root)
    response = client.get(URL)
    assert response.status_code == 200
    assert response.data == mobile_readiness()
    assert report("ios")["login_ready"] and report("android")["login_ready"]
    assert_no_secret_anywhere(response.json(), secrets)
    forbidden.assert_not_called()
