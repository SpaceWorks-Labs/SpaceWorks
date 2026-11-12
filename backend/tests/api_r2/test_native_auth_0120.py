"""Sign-in on mobile (decision 355), driven through the real attested device flow.

Covers the native gaps the 0.12.0 audit listed: MFA by recovery code, the emailed login
code for an unusual sign-in, sign-up and email verification without a browser, change
password, single-device revocation, typed suspended/restricted answers, uniform
unknown-user refusals and the 429 on the sign-in door.
"""
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle, SimpleRateThrottle

from apps.accounts import services_registration
from apps.accounts.mfa_crypto import recovery_codes
from apps.accounts.models import DeviceGrant, User
from apps.accounts.services_device_tokens import issue_device_token_pair
from tests.accounts.account_factories import device_grant
from tests.accounts.login_risk_helpers import PASSWORD as RISK_PASSWORD, code_from, mail, person  # noqa: F401
from tests.accounts.mfa_helpers import enrolled
from tests.accounts.test_device_auth import attested_login
from tests.return_helpers import make_user

pytestmark = pytest.mark.django_db

ME = "/api/v1/auth/me"
VERIFY = "/api/v1/auth/mfa/verify"
REFRESH = "/api/v1/auth/device/refresh"
PASSWORD = "strong-device-password"
SIGNUP_PASSWORD = "Safe member password 947!"  # sign-up runs the real password validators


@pytest.fixture(autouse=True)
def native_settings(settings):
    settings.PASSWORD_BREACH_CHECK_ENABLED = False
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode()  # MFA secrets are encrypted at rest


def _bearer(access):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


def _account(username):
    return make_user(username, password=PASSWORD, access_status=User.AccessStatus.ACTIVE)


def test_recovery_code_finishes_a_native_mfa_sign_in(settings, monkeypatch):
    user = _account("native-auth-recovery")
    codes, digests = recovery_codes()
    enrolled(user, recovery_digests=digests)
    client = APIClient()
    first, _ = attested_login(client, user, settings, monkeypatch)
    assert first.status_code == 200 and first.data["mfa_required"] is True and "access" not in first.data
    done = client.post(VERIFY, {"challenge": first.data["challenge"], "code": codes[0]}, format="json")
    assert done.status_code == 200, done.data
    assert done.data["device_grant"] and "refresh_token" not in done.cookies
    assert client.post(REFRESH, {"refresh": done.data["refresh"]}, format="json").status_code == 200


def test_unusual_native_sign_in_is_finished_by_the_emailed_code(settings, monkeypatch, mail,  # noqa: F811
                                                                django_capture_on_commit_callbacks):
    user = person("native-auth-risk")
    client = APIClient()
    with django_capture_on_commit_callbacks(execute=True):
        first, _ = attested_login(client, user, settings, monkeypatch, password=RISK_PASSWORD)
    assert first.status_code == 200, first.data
    assert first.data["purpose"] == "risk" and first.data["factors"] == ["email_code"]
    with django_capture_on_commit_callbacks(execute=True):
        done = client.post(VERIFY, {"challenge": first.data["challenge"], "code": code_from(mail),
                                    "factor": "email_code"}, format="json")
    assert done.status_code == 200, done.data
    assert done.data["device_grant"] and done.data["refresh"]
    assert _bearer(done.data["access"]).get(ME).status_code == 200


def test_sign_up_and_email_verification_complete_without_a_browser(settings, monkeypatch):
    settings.INFRA_HOSTS = {*settings.INFRA_HOSTS, "testserver"}
    codes = []
    monkeypatch.setattr(services_registration, "send_email_verification_otp",
                        lambda _user, code: codes.append(code) or 1)
    signup = APIClient().post("/api/v1/auth/member-sign-up", {
        "display_name": "Native Ada", "email": "native-ada@example.test", "password": SIGNUP_PASSWORD},
        format="json")
    assert signup.status_code == 200, signup.data
    user = User.objects.get(email="native-ada@example.test")
    login, _ = attested_login(APIClient(), user, settings, monkeypatch, password=SIGNUP_PASSWORD)
    assert login.status_code == 200, login.data
    phone = _bearer(login.data["access"])
    blocked = phone.get("/api/v1/auth/mfa")
    assert blocked.status_code == 403 and blocked.data["code"] == "email_verification_required"
    assert phone.post("/api/v1/auth/email-verification/confirm", {"code": codes[-1]},
                      format="json").status_code == 200
    assert phone.get("/api/v1/auth/mfa").status_code == 200  # the same device session is now a member


def test_change_password_from_the_phone_signs_every_session_out(settings, monkeypatch):
    user = _account("native-auth-change")
    login, _ = attested_login(APIClient(), user, settings, monkeypatch)
    phone = _bearer(login.data["access"])
    changed = phone.post("/api/v1/auth/change-password", {
        "current_password": PASSWORD, "new_password": "Another native password 512!"}, format="json")
    assert changed.status_code == 200, changed.data
    assert phone.get(ME).status_code == 401
    assert APIClient().post(REFRESH, {"refresh": login.data["refresh"]}, format="json").status_code == 401
    assert DeviceGrant.objects.get(pk=login.data["device_grant"]["id"]).status == DeviceGrant.Status.REVOKED


def test_revoking_one_device_ends_only_that_device():
    user = _account("native-auth-revoke-one")
    keep = device_grant(user)
    other = device_grant(user, platform="apple", app_id="org.spaceworks.app")
    keep_client = _bearer(issue_device_token_pair(user, keep)[0])
    other_client = _bearer(issue_device_token_pair(user, other)[0])
    listed = keep_client.get("/api/v1/auth/device/grants")
    assert listed.status_code == 200
    assert keep_client.delete(f"/api/v1/auth/device/grants/{other.pk}").status_code == 204
    assert other_client.get(ME).status_code == 401
    assert keep_client.get(ME).status_code == 200


@pytest.mark.parametrize("access_status,code", [
    (User.AccessStatus.SUSPENDED, "account_suspended"),
    (User.AccessStatus.RESTRICTED, "account_restricted"),
])
def test_suspended_or_restricted_account_gets_a_typed_401(access_status, code):
    user = _account(f"native-auth-{access_status}")
    phone = _bearer(issue_device_token_pair(user, device_grant(user))[0])
    assert phone.get(ME).status_code == 200
    User.objects.filter(pk=user.pk).update(access_status=access_status)
    refused = phone.get(ME)
    assert refused.status_code == 401 and refused.data["code"] == code


def test_unknown_account_and_wrong_password_get_the_same_refusal(settings, monkeypatch):
    user = _account("native-auth-uniform")
    wrong, _ = attested_login(APIClient(), user, settings, monkeypatch, password="not-the-password-1!")
    unknown, _ = attested_login(APIClient(), SimpleNamespace(username="no-such-native-person"),
                                settings, monkeypatch, password="not-the-password-1!")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.data == unknown.data


def test_native_sign_in_door_answers_429_with_retry_after(settings, monkeypatch):
    rates = {**SimpleRateThrottle.THROTTLE_RATES, "device_login": "1/hour"}
    monkeypatch.setattr(SimpleRateThrottle, "THROTTLE_RATES", rates)
    monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", rates)
    user = _account("native-auth-throttle")
    attested_login(APIClient(), user, settings, monkeypatch)
    refused, _ = attested_login(APIClient(), user, settings, monkeypatch)
    assert refused.status_code == 429 and int(refused["Retry-After"]) >= 1
