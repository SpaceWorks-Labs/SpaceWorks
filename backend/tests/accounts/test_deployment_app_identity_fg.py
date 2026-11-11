"""One logical deployment app, public identity discovery and write-only secrets."""
import json

import pytest
from django.db import IntegrityError, transaction
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.forms_native_apps import NativeAppRegistrationForm
from apps.accounts.models import NativeAppRegistration, User
from apps.accounts.models_attestation import PlatformAttestationSettings
from apps.audit.models import AuditLog
from tests.accounts.control_mfa_helpers import force_control_mfa_login
from tests.accounts.mobile_integration_helpers import APP, FIRST, SECOND, PREFIX, registration
from tests.accounts.test_native_registration_m1e import registration_data
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db


def test_native_identity_defaults_and_production_only_contract():
    make_space("fg-public-native")
    native = APIClient().get("/api/v1/config").data["native"]
    assert native["app_display_name"] == "SpaceWorks"
    assert native["app_identity"] == {"android": None, "ios": None}
    assert not PlatformAttestationSettings.objects.exists()  # Public reads do not create settings.
    registration(environment="development")
    registration("apple", status="pending")
    registration(makerspace=make_space("fg-inert-native"))
    assert APIClient().get("/api/v1/config").data["native"]["app_identity"] == {"android": None, "ios": None}


def test_public_identity_follows_validated_signer_rotation_without_leaking_credentials():
    make_space("fg-native-rotation")
    row = registration(signing_identities=[FIRST])
    apple = registration("apple")
    settings = PlatformAttestationSettings.load()
    settings.app_display_name = "Community Works"
    settings.set_play_integrity_service_account("private-test-credential")
    settings.save()
    form = NativeAppRegistrationForm(instance=row, data=registration_data(
        app_id=APP, signing_identities=json.dumps([FIRST.upper(), ":".join(["CD"] * 32)])))
    assert form.is_valid(), form.errors
    form.save()
    response = APIClient().get("/api/v1/config")
    native = response.data["native"]
    assert native["app_display_name"] == "Community Works"
    assert native["app_identity"] == {"android": {"app_id": APP, "signing_identities": [FIRST, SECOND]},
                                      "ios": {"app_id": apple.app_id, "signing_identities": [PREFIX]}}
    assert "private-test-credential" not in str(response.data)
    assert settings.play_integrity_service_account not in str(response.data)
    assert "verifier_config_key" not in str(response.data)
    row.status = "revoked"
    row.save(update_fields=["status"])
    assert APIClient().get("/api/v1/config").data["native"]["app_identity"]["android"] is None


@pytest.mark.parametrize("platform", ["android", "apple"])
@pytest.mark.parametrize("environment", ["production", "development"])
def test_duplicate_approved_identity_is_rejected_in_form_and_database(platform, environment):
    row = registration(platform, environment=environment)
    form = NativeAppRegistrationForm(data=registration_data(app_id="org.example.second",
        platform=platform, environment=environment,
        signing_identities=json.dumps([PREFIX] if platform == "apple" else [FIRST])))
    assert not form.is_valid() and "Only one approved deployment app" in str(form.errors)
    with pytest.raises(IntegrityError), transaction.atomic():
        NativeAppRegistration.objects.create(platform=platform, environment=environment,
            app_id="org.example.second", verifier_config_key="second", status="approved")
    replacement = registration(platform, environment=environment, app_id="org.example.second", status="pending")
    row.status = "revoked"
    row.save(update_fields=["status"])
    replacement.status = "approved"
    replacement.full_clean()
    replacement.save()
    assert NativeAppRegistration.objects.filter(platform=platform, environment=environment,
                                               makerspace__isnull=True, status="approved").count() == 1


def test_control_name_edit_preserves_encrypted_credentials_and_audits(client):
    actor = User.objects.create_superuser(username="fg-app-control", password="strong-control-password")
    force_control_mfa_login(client, actor)
    row = PlatformAttestationSettings.load()
    row.set_play_integrity_service_account("secret-preserved-on-name-edit")
    row.save()
    encrypted = row.play_integrity_service_account
    path = reverse("admin:accounts_platformattestationsettings_change", args=[1])
    response = client.post(path, {"app_display_name": "Our Community App", "play_integrity_service_account_raw": ""})
    assert response.status_code == 302
    row.refresh_from_db()
    assert row.app_display_name == "Our Community App" and row.play_integrity_service_account == encrypted
    assert row.get_play_integrity_service_account() == "secret-preserved-on-name-edit"
    event = AuditLog.objects.get(action="platform.attestation_settings_updated", actor=actor)
    assert "app_display_name" in event.meta["changed_fields"]
    response = client.get(path)
    assert b"secret-preserved-on-name-edit" not in response.content
    assert encrypted.encode() not in response.content
    invalid = client.post(path, {"app_display_name": " ", "play_integrity_service_account_raw": ""})
    assert invalid.status_code == 200 and "app_display_name" in invalid.context["adminform"].form.errors
