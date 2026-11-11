"""S-B: the unusual-login check (#62, Q4, Q13; #66 superadmin alerts only)."""

from django.conf import settings
import pytest
from django.core.cache import cache
from django.test import RequestFactory
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts import device_memory, login_risk
from apps.accounts.models import KnownDevice, KnownNetwork, SecurityAlert, User
from apps.audit.models import AuditLog
from apps.makerspaces import security_policy_store
from tests.accounts.account_factories import grant_staff_role
from tests.accounts.login_risk_helpers import ORIGIN, code_from, login, mail, person  # noqa: F401
from tests.accounts.mfa_helpers import enrolled
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db


def _signed_in_with_code(client, user, mail, capture):
    with capture(execute=True):
        first = login(client, user)
    assert first.status_code == 200, first.data
    assert first.data["purpose"] == "risk" and first.data["factors"] == ["email_code"]
    assert first.data["enrollment_required"] is False
    with capture(execute=True):
        done = client.post("/api/v1/auth/mfa/verify", {"challenge": first.data["challenge"], "code": code_from(mail),
                           "factor": "email_code"}, format="json", HTTP_ORIGIN=ORIGIN)
    assert done.status_code == 200, done.data
    return done


def test_new_device_password_sign_in_needs_an_emailed_code(mail, django_capture_on_commit_callbacks):
    user = person()
    client = APIClient()
    done = _signed_in_with_code(client, user, mail, django_capture_on_commit_callbacks)
    claims = AccessToken(done.data["access"])
    assert claims["mfa_source"] == "email_code" and "mfa_method" not in claims  # never VERIFIED
    assert done.cookies["sw_device"]["httponly"] and done.cookies["sw_device"]["samesite"] == settings.AUTH_COOKIE_SAMESITE
    assert KnownDevice.objects.filter(user=user, revoked_at__isnull=True).count() == 1
    assert KnownNetwork.objects.filter(user=user).count() == 1
    assert AuditLog.objects.filter(action="auth.login_risk_challenged", actor=user).exists()
    assert AuditLog.objects.filter(action="auth.login_code_sent", actor=user).exists()
    # The same browser and network next time: no step-up.
    client.cookies["sw_device"] = done.cookies["sw_device"].value
    again = login(client, user)
    assert again.status_code == 200 and "access" in again.data, again.data


def test_wrong_code_is_counted_and_refused(mail, django_capture_on_commit_callbacks):
    user = person("risk-wrong")
    with django_capture_on_commit_callbacks(execute=True):
        first = login(APIClient(), user)
    wrong = APIClient().post("/api/v1/auth/mfa/verify", {"challenge": first.data["challenge"], "code": "000000"},
                             format="json", HTTP_ORIGIN=ORIGIN)
    assert wrong.status_code == 400 and wrong.data["code"] == "login_code_invalid"
    assert AuditLog.objects.filter(action="auth.login_code_failed", actor=user).exists()


def test_resend_replaces_the_code_at_most_twice(mail, django_capture_on_commit_callbacks):
    user = person("risk-resend")
    with django_capture_on_commit_callbacks(execute=True):
        first = login(APIClient(), user)
    old = code_from(mail)
    for left in (1, 0):
        with django_capture_on_commit_callbacks(execute=True):
            again = APIClient().post("/api/v1/auth/login-code/resend", {"challenge": first.data["challenge"]},
                                     format="json", HTTP_ORIGIN=ORIGIN)
        assert again.status_code == 200 and again.data["resends_left"] == left, again.data
    third = APIClient().post("/api/v1/auth/login-code/resend", {"challenge": first.data["challenge"]},
                             format="json", HTTP_ORIGIN=ORIGIN)
    assert third.status_code == 400 and third.data["code"] == "login_code_invalid"
    stale = APIClient().post("/api/v1/auth/mfa/verify", {"challenge": first.data["challenge"], "code": old},
                             format="json", HTTP_ORIGIN=ORIGIN)
    assert stale.status_code == 400 or code_from(mail) == old


def test_code_works_with_two_step_switch_off(mail, django_capture_on_commit_callbacks, monkeypatch):
    monkeypatch.setattr("apps.accounts.mfa_policy.mfa_login_enabled", lambda: False)
    user = person("risk-switch-off")
    done = _signed_in_with_code(APIClient(), user, mail, django_capture_on_commit_callbacks)
    assert AccessToken(done.data["access"])["mfa_source"] == "email_code"


def test_no_channel_fails_open_and_is_audited(settings, monkeypatch):
    settings.AUTH_COOKIE_SECURE = False
    cache.clear()
    monkeypatch.setattr("apps.integrations.email.email_enabled", lambda: False)
    user = person("risk-open")
    response = login(APIClient(), user)
    assert response.status_code == 200 and "access" in response.data
    assert AuditLog.objects.filter(action="auth.risk_unverifiable", actor=user).exists()


def test_failures_in_the_last_hour_trigger_even_on_a_known_device(mail, django_capture_on_commit_callbacks):
    user = person("risk-failures")
    client = APIClient()
    done = _signed_in_with_code(client, user, mail, django_capture_on_commit_callbacks)
    client.cookies["sw_device"] = done.cookies["sw_device"].value
    for _ in range(3):
        client.post("/api/v1/auth/login", {"username": user.username, "password": "wrong"}, format="json",
                    HTTP_ORIGIN=ORIGIN)
    with django_capture_on_commit_callbacks(execute=True):
        again = login(client, user)
    assert again.status_code == 200 and again.data.get("purpose") == "risk", again.data


def test_a_space_cannot_loosen_the_platform_check(mail, django_capture_on_commit_callbacks):
    """``security.login_risk_check`` only tightens: the platform default is on, so a space's off
    value never turns the step-up off for its staff (strictest across their spaces)."""
    user = person("risk-policy-off")
    space = make_space("risk-policy-space")
    grant_staff_role(user, space, role_slug="inventory_manager")
    security_policy_store.write(space, "security.login_risk_check", False)
    assert login_risk.check_enabled(user) is True
    with django_capture_on_commit_callbacks(execute=True):
        response = login(APIClient(), user)
    assert response.data.get("purpose") == "risk", response.data


def test_remembered_days_is_the_strictest_across_staff_spaces():
    user = person("risk-days")
    for slug, days in (("risk-days-a", 30), ("risk-days-b", 7)):
        space = make_space(slug)
        grant_staff_role(user, space, role_slug="inventory_manager")
        security_policy_store.write(space, "security.remembered_device_days", days)
    assert device_memory.remembered_days(user) == 7
    assert device_memory.remembered_days(person("risk-days-member")) == 90


def test_a_remembered_device_never_skips_the_authenticator(mail, django_capture_on_commit_callbacks):
    user = person("risk-staff")
    grant_staff_role(user, make_space("risk-staff-space"), role_slug="inventory_manager")
    enrolled(user)
    request = RequestFactory().get("/", REMOTE_ADDR="203.0.113.9")
    _row, token, _ = device_memory.remember(request, user)
    client = APIClient()
    client.cookies["sw_device"] = token
    response = login(client, user)
    assert response.data["mfa_required"] is True and response.data["purpose"] == "login"
    assert response.data["factors"] == ["totp"]


def test_superadmin_is_alerted_never_stepped_up(mail):
    admin = User.objects.create_superuser(username="risk-root", email="root@example.test", password="x",
                                          account_kind="platform", role="superadmin")
    request = RequestFactory().get("/", REMOTE_ADDR="198.51.100.7")
    decision = login_risk.evaluate(request, admin, "password")
    assert decision.unusual and not decision.step_up
    device_memory.remember(RequestFactory().get("/"), admin)  # an earlier device
    login_risk.record_success(request, admin, method="password", web=True)
    assert SecurityAlert.objects.filter(user=admin, kind="new_device").exists()


def test_social_and_phone_record_the_device_without_a_step_up():
    user = person("risk-social")
    request = RequestFactory().get("/", REMOTE_ADDR="198.51.100.8")
    assert not login_risk.evaluate(request, user, "social").step_up
    assert not login_risk.evaluate(request, user, "phone").step_up
    assert login_risk.record_success(request, user, method="social", web=False)
    assert KnownDevice.objects.filter(user=user).count() == 1


def test_device_trust_round_trip_through_the_header():
    user = person("risk-native")
    first = RequestFactory().get("/", REMOTE_ADDR="198.51.100.9")
    token = login_risk.record_success(first, user, method="password", web=False)
    later = RequestFactory().get("/", REMOTE_ADDR="198.51.100.9", HTTP_X_DEVICE_TRUST=token)
    assert device_memory.lookup(later, user) is not None
    assert login_risk.evaluate(later, user, "password").reasons == ()
    forged = RequestFactory().get("/", HTTP_X_DEVICE_TRUST=token[:-2] + "xx")
    assert device_memory.lookup(forged, user) is None


def test_refresh_never_evaluates_risk(mail, django_capture_on_commit_callbacks, monkeypatch):
    user = person("risk-refresh")
    client = APIClient()
    _signed_in_with_code(client, user, mail, django_capture_on_commit_callbacks)
    monkeypatch.setattr(login_risk, "evaluate", lambda *a, **k: pytest.fail("refresh evaluated risk"))
    refreshed = client.post("/api/v1/auth/refresh", {}, format="json", HTTP_ORIGIN=ORIGIN, HTTP_X_REFRESH_CSRF="1")
    assert refreshed.status_code == 200, refreshed.data
