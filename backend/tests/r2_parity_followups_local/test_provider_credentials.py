"""#190 follow-up: platform provider credentials in the web console. Local only."""

from unittest import mock

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.integrations.models_push import PlatformPushSettings
from apps.integrations.models_sms import PlatformSmsSettings
from tests.r2_superadmin_local.helpers import api, manager, space, superadmin

pytestmark = pytest.mark.django_db
A = "/api/v1/admin/platform/"


@pytest.fixture
def root():
    cache.clear()
    return superadmin("providers-root")


def test_staff_and_unreauthenticated_superadmins_are_refused(root):
    boss = manager(space("providers-staff"))
    for path in ("sms-settings", "push-settings", "whatsapp-settings", "attestation-settings"):
        assert api(boss).get(A + path).status_code in {401, 403}, path
    stale = APIClient(HTTP_HOST="localhost")
    stale.force_authenticate(user=root)
    response = stale.patch(A + "sms-settings", {"account_sid": "AC1"}, format="json")
    assert response.status_code == 403
    assert not PlatformSmsSettings.objects.exists()


def test_a_read_creates_nothing_and_says_not_set(root):
    body = api(root).get(A + "push-settings").json()
    assert body["provider"] == "push" and body["test"] == "check" and body["updated_at"] is None
    assert {row["name"]: row["set"] for row in body["secrets"]} == {"fcm_service_account": False, "apns_private_key": False}
    assert not PlatformPushSettings.objects.exists()


def test_sms_secret_is_stored_encrypted_never_returned_and_audited_by_field(root):
    client = api(root)
    response = client.patch(A + "sms-settings", {"account_sid": "AC123", "auth_token": "s3cret-token",
                                                 "from_number": "+447700900123"}, format="json")
    assert response.status_code == 200, response.json()
    assert "s3cret-token" not in response.content.decode()
    row = PlatformSmsSettings.objects.get(pk=1)
    assert row.auth_token != "s3cret-token" and row.get_auth_token() == "s3cret-token"
    secret = response.json()["secrets"][0]
    assert secret["set"] is True and secret["last_changed"]["by"] == root.username
    log = AuditLog.objects.get(action="platform.sms_settings_updated")
    assert log.meta["via"] == "console" and "auth_token_raw" in log.meta["changed_fields"]
    assert "s3cret-token" not in str(log.meta)
    # A blank secret keeps it; clearing removes it.
    assert client.patch(A + "sms-settings", {"account_sid": "AC124"}, format="json").status_code == 200
    assert PlatformSmsSettings.objects.get(pk=1).get_auth_token() == "s3cret-token"
    assert client.patch(A + "sms-settings", {"clear_auth_token": True}, format="json").json()["secrets"][0]["set"] is False


def test_the_control_form_validation_answers_in_api_field_names(root):
    response = api(root).patch(A + "sms-settings", {"from_number": "not a number"}, format="json")
    assert response.status_code == 400 and "from_number" in response.json()
    bad = api(root).patch(A + "attestation-settings", {"play_integrity_service_account": "{}"}, format="json")
    assert bad.status_code == 400 and "play_integrity_service_account" in bad.json()
    meta = api(root).patch(A + "whatsapp-settings", {"app_id": "abc"}, format="json")
    assert meta.status_code == 400 and "app_id" in meta.json()


def test_sms_test_sends_once_and_fails_safe(root):
    client = api(root)
    assert client.post(A + "sms-settings/test", {"to": "+447700900111"}, format="json").json()["code"] == "provider_not_configured"
    client.patch(A + "sms-settings", {"account_sid": "AC1", "auth_token": "t", "from_number": "+447700900123"}, format="json")
    with mock.patch("apps.integrations.sms.twilio.TwilioSmsProvider.send", return_value=True) as send:
        assert client.post(A + "sms-settings/test", {"to": "+447700900111"}, format="json").json() == {"outcome": "sent"}
    assert send.call_args.kwargs["to"] == "+447700900111"
    with mock.patch("apps.integrations.sms.twilio.TwilioSmsProvider.send", return_value=False):
        failed = client.post(A + "sms-settings/test", {"to": "+447700900111"}, format="json")
    assert failed.status_code == 503 and failed.json()["code"] == "provider_test_failed"
    outcomes = list(AuditLog.objects.filter(action="platform.provider_test").order_by("pk").values_list("meta__outcome", flat=True))
    assert outcomes == ["provider_not_configured", "sent", "provider_test_failed"]
    assert "+447700900111" not in str(list(AuditLog.objects.values_list("meta", flat=True)))
    assert client.post(A + "sms-settings/test", {"to": "nope"}, format="json").status_code == 400


def test_push_and_whatsapp_checks(root):
    client = api(root)
    assert client.post(A + "push-settings/test").status_code == 409
    PlatformPushSettings.objects.create(pk=1)
    row = PlatformPushSettings.objects.get(pk=1)
    row.set_fcm_service_account('{"x": 1}')
    row.save()
    with mock.patch("apps.integrations.push_fcm.fcm_access_token", return_value=("tok", "proj")):
        assert client.post(A + "push-settings/test").json() == {"outcome": "ok", "checked": ["fcm"]}
    failed = client.post(A + "push-settings/test")  # the stored account is not a service account
    assert failed.status_code == 503 and failed.json()["code"] == "provider_test_failed"
    assert client.post(A + "whatsapp-settings/test").json()["code"] == "provider_not_configured"
    client.patch(A + "whatsapp-settings", {"phone_number_id": "123", "access_token": "tok"}, format="json")
    with mock.patch("apps.integrations.platform_credential_checks.requests.get") as get:
        get.return_value.status_code = 200
        assert client.post(A + "whatsapp-settings/test").json()["outcome"] == "ok"
        get.return_value.status_code = 401
        assert client.post(A + "whatsapp-settings/test").status_code == 503
    body = client.get(A + "whatsapp-settings").json()
    assert "callback_url" in body["info"] and "tok" not in str(body["values"])


def test_login_methods_change_only_the_writable_switches(root):
    from apps.accounts.models_login_methods import PlatformLoginMethods
    client = api(root)
    saved = client.patch(A + "login-methods", {"self_registration_enabled": False}, format="json")
    assert saved.status_code == 200, saved.json()
    row = PlatformLoginMethods.objects.get(pk=1)
    assert row.self_registration_enabled is False and row.mfa_enabled == PlatformLoginMethods().mfa_enabled
    assert client.patch(A + "login-methods", {"mfa_enabled": False}, format="json").status_code == 200
    assert PlatformLoginMethods.objects.get(pk=1).mfa_enabled == PlatformLoginMethods().mfa_enabled
    assert AuditLog.objects.filter(action="platform.login_methods_updated", meta__via="console").count() == 2
