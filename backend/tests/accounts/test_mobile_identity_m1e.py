import importlib
from types import SimpleNamespace

import pytest
from django.apps import apps
from django.contrib import admin
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.attestation import AttestationUnavailable, configured_app, create_challenge
from apps.accounts.checks import check_legacy_native_identities
from apps.accounts.forms_native_apps import NativeAppRegistrationForm
from apps.accounts.models_devices import DeviceAttestationChallenge, NativeAppRegistration
from apps.accounts.native_app_identity import min_app_versions
from apps.audit.models import AuditLog
from tests.accounts.control_mfa_helpers import force_control_mfa_login
from tests.accounts.mobile_integration_helpers import APP, FIRST, PREFIX, SECOND, registration
from tests.return_helpers import make_space, make_user

pytestmark = pytest.mark.django_db


def form_data(**overrides):
    values = {"app_id": APP, "platform": "android", "environment": "production",
              "status": "approved", "verifier_config_key": APP,
              "signing_identities": [FIRST, SECOND], "min_supported_version": "1.10.0"}
    values.update(overrides)
    return values


@pytest.mark.parametrize("overrides,field", [
    ({"app_id": "no dots"}, "app_id"),
    ({"app_id": "org.1invalid"}, "app_id"),
    ({"signing_identities": []}, "signing_identities"),
    ({"signing_identities": [FIRST] * 6}, "signing_identities"),
    ({"signing_identities": {"digest": FIRST}}, "signing_identities"),
    ({"signing_identities": ["ab:cd"]}, "signing_identities"),
    ({"platform": "apple", "signing_identities": ["short"]}, "signing_identities"),
    ({"platform": "apple", "signing_identities": [PREFIX, PREFIX]}, "signing_identities"),
    ({"platform": "apple", "signing_identities": ["teamid1234"]}, "signing_identities"),
    ({"platform": "apple", "app_id": "org.invalid_bundle", "signing_identities": [PREFIX]}, "app_id"),
    ({"min_supported_version": "v1.2"}, "min_supported_version"),
    ({"min_supported_version": "1.2-beta"}, "min_supported_version"),
])
def test_registration_form_rejects_invalid_values(overrides, field):
    form = NativeAppRegistrationForm(data=form_data(**overrides))
    assert not form.is_valid()
    assert field in form.errors


def test_form_normalises_distribution_signers_and_optional_version():
    colon = ":".join(["AB"] * 32)
    form = NativeAppRegistrationForm(data=form_data(signing_identities=[colon, SECOND], min_supported_version=""))
    assert form.is_valid(), form.errors
    row = form.save()
    assert row.signing_identities == [FIRST, SECOND]
    assert row.min_supported_version is None


def test_stored_identity_wins_and_challenge_copies_the_list(settings):
    row = registration("apple")
    settings.DEVICE_ATTESTATION_APPS = {"apple": {APP: {
        "signing_identity": "OTHER12345", "environments": ["production"],
    }}}
    settings.DEVICE_APPLE_ATTESTATION_VERIFY_URL = ""
    settings.DEVICE_APPLE_ATTESTATION_VERIFY_TOKEN = ""
    assert configured_app("apple", APP, "production") == PREFIX
    raw = create_challenge(platform="apple", app_id=APP, environment="production")
    challenge = DeviceAttestationChallenge.objects.latest("pk")
    assert raw and challenge.signing_identity == PREFIX
    assert challenge.signing_identities == [PREFIX]
    row.signing_identities = ["OTHER12345"]
    row.save()
    challenge.refresh_from_db()
    assert challenge.signing_identities == [PREFIX]


def test_legacy_fallback_warns_and_invalid_stored_identity_cannot_fall_back(settings):
    row = registration("apple", signing_identities=[])
    settings.DEVICE_ATTESTATION_APPS = {"apple": {APP: {
        "signing_identity": PREFIX, "environments": ["production"],
    }}}
    settings.DEVICE_APPLE_ATTESTATION_VERIFY_URL = ""
    settings.DEVICE_APPLE_ATTESTATION_VERIFY_TOKEN = ""
    assert configured_app("apple", APP, "production") == PREFIX
    warning = check_legacy_native_identities()[0]
    assert warning.id == "accounts.W001" and f"#{row.pk}" in warning.msg
    row.signing_identities = ["invalid"]
    row.save()
    with pytest.raises(AttestationUnavailable):
        configured_app("apple", APP, "production")
    assert check_legacy_native_identities() == []


def test_android_challenge_snapshots_all_signers(settings):
    registration()
    settings.DEVICE_ANDROID_ATTESTATION_VERIFY_URL = "https://verifier.example.test"
    settings.DEVICE_ANDROID_ATTESTATION_VERIFY_TOKEN = "private-token"
    create_challenge(platform="android", app_id=APP, environment="production")
    challenge = DeviceAttestationChallenge.objects.latest("pk")
    assert challenge.signing_identity == FIRST
    assert challenge.signing_identities == [FIRST, SECOND]


def test_numeric_minimum_uses_only_global_approved_production_registrations():
    registration(min_supported_version="1.9.99", status="revoked")
    registration(app_id="org.example.new", min_supported_version="1.10.0")
    registration("apple", min_supported_version="2.3")
    registration(environment="development", min_supported_version="99.0")
    registration(app_id="org.example.revoked", status="revoked", min_supported_version="100.0")
    registration(app_id="org.example.pending", status="pending", min_supported_version="100.0")
    registration(makerspace=make_space("minimum-tenant"), min_supported_version="200.0")
    assert min_app_versions() == {"android": "1.10.0", "ios": "2.3"}


def test_data_migration_backfills_only_available_legacy_identity_and_snapshots_challenges(settings):
    legacy = registration(signing_identities=[])
    missing = registration("apple", signing_identities=[])
    settings.DEVICE_ATTESTATION_APPS = {"android": {APP: {
        "signing_identity": FIRST.upper(), "environments": ["production"],
    }}}
    challenge = DeviceAttestationChallenge.objects.create(
        registration=legacy, platform="android", app_id=APP, environment="production",
        signing_identity=SECOND, challenge_digest="a" * 64, expires_at=timezone.now(),
    )
    migration = importlib.import_module("apps.accounts.migrations.0035_mobile_app_identity")
    migration.backfill_identities(apps, SimpleNamespace(connection=SimpleNamespace(alias="default")))
    legacy.refresh_from_db()
    missing.refresh_from_db()
    challenge.refresh_from_db()
    assert legacy.signing_identities == [FIRST]
    assert missing.signing_identities == []
    assert challenge.signing_identities == [SECOND]


def test_every_admin_save_is_audited_and_revocation_uses_the_service():
    actor = make_user("registration-editor", is_superuser=True, is_staff=True)
    client = Client()
    force_control_mfa_login(client, actor)
    add = reverse("admin:accounts_nativeappregistration_add")
    data = form_data(signing_identities='["' + FIRST + '"]')
    saved = client.post(add, data)
    changelist = reverse("admin:accounts_nativeappregistration_changelist")
    assert saved.status_code == 302
    assert saved.url == changelist
    row = NativeAppRegistration.objects.get(app_id=APP)
    change = reverse("admin:accounts_nativeappregistration_change", args=[row.pk])
    for version in ("2.0", "2.1"):
        saved = client.post(change, {**data, "min_supported_version": version})
        assert saved.status_code == 302
        assert saved.url == changelist
    events = AuditLog.objects.filter(action="native_app.registration_updated", actor=actor)
    assert events.count() == 3
    assert all(event.meta["via"] == "control" for event in events)
    saved = client.post(change, {**data, "status": "revoked"})
    assert saved.status_code == 302
    assert saved.url == changelist
    assert AuditLog.objects.filter(action="native_app.revoked", actor=actor).exists()
    assert not admin.site._registry[NativeAppRegistration].has_delete_permission(SimpleNamespace(user=actor), row)
