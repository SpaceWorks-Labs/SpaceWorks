"""S-B: security alerts and the single-use "this wasn't me" link (#62)."""

from datetime import timedelta

import pytest
from django.test import RequestFactory
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts import device_memory, security_alerts
from apps.accounts.models import KnownDevice, SecurityAlert
from apps.accounts.models_mfa import UserMFA
from apps.accounts.security_signals import send_mfa_changed
from apps.audit.models import AuditLog
from tests.accounts.login_risk_helpers import ORIGIN, PASSWORD, mail, person  # noqa: F401
from tests.accounts.mfa_helpers import enrolled

pytestmark = pytest.mark.django_db
NOT_ME = "/api/v1/auth/security-alerts/not-me"


def _sent_alert(user, mail, capture, kind="new_device"):
    with capture(execute=True):
        row = security_alerts.create(user, kind, network_label="198.51.100.0/24", ua_label="Firefox on Windows")
    item = next(m for m in mail if m["event"].startswith("security_") and m["event"] != "security_login_code")
    token = item["text_body"].split("#token=", 1)[1].split()[0]
    return SecurityAlert.objects.get(pk=row.pk), item, token


def test_alert_mail_is_platform_mail_and_labels_are_cleared_after_send(mail, django_capture_on_commit_callbacks):
    user = person("alert-labels")
    row, item, token = _sent_alert(user, mail, django_capture_on_commit_callbacks)
    assert item["makerspace"] is None and item["stream"] == "account" and item["persist_body"] is False
    assert "Firefox on Windows" in item["text_body"] and "https://app.example.test/security/not-me#token=" in item["html_body"]
    assert "?token" not in item["text_body"]
    assert row.network_label is None and row.ua_label is None and not row.nonce_digest.startswith("p")
    assert token not in str(list(AuditLog.objects.values_list("meta", flat=True)))
    from apps.integrations.dispatch import EMAIL_MODULE_EXEMPT
    assert ("account", item["event"]) in EMAIL_MODULE_EXEMPT


def test_not_me_signs_out_everywhere_and_keeps_factors(mail, django_capture_on_commit_callbacks, monkeypatch):
    user = person("alert-not-me")
    enrolled(user)
    RefreshToken.for_user(user)
    device_memory.remember(RequestFactory().get("/"), user)
    other = security_alerts.create(user, "password_changed")
    resets = []
    monkeypatch.setattr("apps.accounts.services_password_reset.request_password_reset",
                        lambda email, **kw: resets.append((email, kw["context"])))
    _row, _item, token = _sent_alert(user, mail, django_capture_on_commit_callbacks)
    client = APIClient()
    with django_capture_on_commit_callbacks(execute=True):
        used = client.post(NOT_ME, {"token": token}, format="json", HTTP_ORIGIN=ORIGIN)
    assert used.status_code == 200, used.data
    assert used.data["signed_out"] is True and used.data["mfa_reset"]["superadmin"] is True
    user.refresh_from_db()
    assert not user.has_usable_password()
    assert UserMFA.objects.get(user=user).enabled_at is not None  # no factor removed
    assert OutstandingToken.objects.filter(user=user).count() == BlacklistedToken.objects.filter(
        token__user=user).count()
    assert not KnownDevice.objects.filter(user=user, revoked_at__isnull=True).exists()
    assert SecurityAlert.objects.get(pk=other.pk).used_at is not None
    assert resets == [(user.email, "member")]
    assert AuditLog.objects.filter(action="auth.not_me_used", actor=user).exists()
    again = APIClient().post(NOT_ME, {"token": token}, format="json", HTTP_ORIGIN=ORIGIN)
    assert again.status_code == 400 and again.data["code"] == "security_alert_used"


def test_not_me_is_token_only(mail, django_capture_on_commit_callbacks):
    user = person("alert-token-only")
    _row, _item, token = _sent_alert(user, mail, django_capture_on_commit_callbacks)
    assert APIClient().get(f"{NOT_ME}?token={token}").status_code == 405
    forged = APIClient().post(NOT_ME, {"token": token[:-3] + "abc"}, format="json")
    assert forged.status_code == 400 and forged.data["code"] == "security_alert_used"
    from apps.accounts.views_security_alerts import SecurityAlertNotMeView
    assert SecurityAlertNotMeView.authentication_classes == []


def test_expired_alert_is_refused(mail, django_capture_on_commit_callbacks):
    user = person("alert-expired")
    row, _item, token = _sent_alert(user, mail, django_capture_on_commit_callbacks)
    SecurityAlert.objects.filter(pk=row.pk).update(sent_at=timezone.now() - timedelta(days=20),
                                                   expires_at=timezone.now() - timedelta(seconds=1))
    response = APIClient().post(NOT_ME, {"token": token}, format="json")
    assert response.status_code == 400 and response.data["code"] == "security_alert_used"


def test_completing_a_reset_expires_every_outstanding_alert(mail, django_capture_on_commit_callbacks):
    from apps.accounts.services_password_reset_confirmation import alert_reset
    user = person("alert-reset")
    row, _item, token = _sent_alert(user, mail, django_capture_on_commit_callbacks)
    alert_reset(user)
    assert SecurityAlert.objects.get(pk=row.pk).used_at is not None
    assert APIClient().post(NOT_ME, {"token": token}, format="json").status_code == 400
    assert SecurityAlert.objects.filter(user=user, kind="password_changed", used_at__isnull=True).exists()


def test_mfa_change_and_lockout_alerts(mail, django_capture_on_commit_callbacks):
    user = person("alert-kinds")
    with django_capture_on_commit_callbacks(execute=True):
        send_mfa_changed(user, "totp_enabled")
    assert SecurityAlert.objects.filter(user=user, kind="mfa_changed").count() == 1
    assert security_alerts.account_locked(user) is not None
    assert security_alerts.account_locked(user) is None  # at most one an hour


def test_password_change_alerts_and_keeps_the_changing_device(mail, django_capture_on_commit_callbacks):
    user = person("alert-change")
    request = RequestFactory().get("/")
    current, token, _ = device_memory.remember(request, user)
    other, _, _ = device_memory.remember(RequestFactory().get("/"), user)
    client = APIClient()
    client.force_authenticate(user)
    client.cookies["sw_device"] = token
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post("/api/v1/auth/change-password", {
            "current_password": PASSWORD, "new_password": "A-new-password-987!"}, format="json")
    assert response.status_code == 200, response.data
    assert KnownDevice.objects.get(pk=current.pk).revoked_at is None
    assert KnownDevice.objects.get(pk=other.pk).revoked_at is not None
    assert SecurityAlert.objects.filter(user=user, kind="password_changed").exists()
