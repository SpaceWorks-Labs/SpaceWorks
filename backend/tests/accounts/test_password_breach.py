"""S-C: the breached-password check (HIBP k-anonymity, padding, fail-open, every seam)."""

import hashlib

import httpx
import pytest
from django.contrib.auth.password_validation import get_default_password_validators, validate_password
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.accounts import password_breach
from apps.accounts.models import User
from apps.audit.models import AuditLog

pytestmark = pytest.mark.django_db
BREACHED = "Correct horse battery staple 1!"
SAFE = "A perfectly unknown passphrase 8114!"


def _suffix(password):
    return hashlib.sha1(password.encode()).hexdigest().upper()[5:]


@pytest.fixture
def hibp(settings, monkeypatch):
    settings.PASSWORD_BREACH_CHECK_ENABLED = True
    seen = []

    def handler(request):
        seen.append(request)
        body = f"{_suffix(BREACHED)}:4211\r\n{'0' * 35}:0\r\n{_suffix(SAFE)[:-1]}X:3"
        return httpx.Response(200, text=body)

    monkeypatch.setattr(password_breach, "_transport", lambda: httpx.MockTransport(handler))
    return seen


def test_only_a_five_character_prefix_leaves_with_padding_requested(hibp):
    assert password_breach.breach_count(BREACHED) == 4211
    request = hibp[0]
    digest = hashlib.sha1(BREACHED.encode()).hexdigest().upper()
    assert str(request.url) == f"https://api.pwnedpasswords.com/range/{digest[:5]}"
    assert request.headers["Add-Padding"] == "true"
    assert digest[5:] not in str(request.url) and not request.content
    assert password_breach.breach_count(SAFE) == 0


def test_padding_rows_never_count(settings, monkeypatch):
    settings.PASSWORD_BREACH_CHECK_ENABLED = True
    monkeypatch.setattr(password_breach, "_transport", lambda: httpx.MockTransport(
        lambda request: httpx.Response(200, text=f"{_suffix(SAFE)}:0")))
    validate_password(SAFE)


@pytest.mark.parametrize("failure", [
    lambda request: (_ for _ in ()).throw(httpx.ConnectTimeout("slow", request=request)),
    lambda request: (_ for _ in ()).throw(httpx.ConnectError("down", request=request)),
    lambda request: httpx.Response(503, text="busy"),
])
def test_fail_open_on_timeout_error_or_bad_status(settings, monkeypatch, failure):
    settings.PASSWORD_BREACH_CHECK_ENABLED = True
    monkeypatch.setattr(password_breach, "_transport", lambda: httpx.MockTransport(failure))
    assert password_breach.breach_count(BREACHED) is None
    validate_password(BREACHED)  # accepted: an outage never blocks a password change


def test_the_validator_runs_through_auth_password_validators_and_uses_the_timeout(settings, monkeypatch, hibp):
    assert any(isinstance(v, password_breach.BreachedPasswordValidator) for v in get_default_password_validators())
    settings.PASSWORD_BREACH_CHECK_TIMEOUT_SECONDS = 2
    captured = {}
    real = httpx.Client

    def client(*args, **kwargs):
        captured["timeout"] = kwargs.get("timeout")
        return real(*args, **kwargs)

    monkeypatch.setattr(password_breach.httpx, "Client", client)
    with pytest.raises(ValidationError) as caught:
        validate_password(BREACHED)
    assert captured["timeout"] == 2 and password_breach.is_breached(caught.value)
    assert AuditLog.objects.filter(action="auth.password_breach_rejected").count() == 1


def test_switch_off_skips_the_network(settings, monkeypatch):
    settings.PASSWORD_BREACH_CHECK_ENABLED = False
    monkeypatch.setattr(password_breach, "_transport", lambda: (_ for _ in ()).throw(AssertionError("network")))
    validate_password(BREACHED)


def test_sign_up_refuses_a_breached_password_with_the_code(hibp, monkeypatch):
    from rest_framework.throttling import ScopedRateThrottle
    monkeypatch.setattr(ScopedRateThrottle, "allow_request", lambda *args: True)
    response = APIClient().post("/api/v1/auth/member-sign-up", {
        "display_name": "Pat", "email": "pat-breach@example.com", "password": BREACHED}, format="json")
    assert response.status_code == 400 and response.json()["code"] == "password_breached"
    assert "password" in response.json()
    assert not User.objects.filter(email="pat-breach@example.com").exists()


def test_change_password_refuses_a_breached_password(hibp):
    person = User.objects.create_user(username="pat-change", password=SAFE)
    from apps.accounts.tokens import SpaceWorksRefreshToken
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {SpaceWorksRefreshToken.for_user(person).access_token}",
                       HTTP_ORIGIN="http://localhost:5000")
    response = client.post("/api/v1/auth/change-password",
                           {"current_password": SAFE, "new_password": BREACHED}, format="json")
    assert response.status_code == 400, response.content
    assert response.json()["code"] == "password_breached" and "new_password" in response.json()
    person.refresh_from_db()
    assert person.check_password(SAFE)


def test_reset_and_restore_confirmation_share_the_validator(hibp):
    from apps.accounts.services_password_reset import validate_recovery_password
    person = User.objects.create_user(username="pat-reset", password=SAFE)
    with pytest.raises(ValidationError) as caught:
        validate_recovery_password(BREACHED, person)
    assert password_breach.error_body("new_password", caught.value)["code"] == "password_breached"


def test_admin_set_passwords_and_the_control_reset_form_refuse_it(hibp):
    from unfold.forms import AdminPasswordChangeForm
    person = User.objects.create_user(username="pat-admin", password=SAFE)
    form = AdminPasswordChangeForm(person, data={"password1": BREACHED, "password2": BREACHED})
    assert not form.is_valid() and "data breach" in str(form.errors)
    with pytest.raises(ValidationError):
        validate_password(BREACHED, user=person)  # admin_api serializers and staff lifecycle call this


def test_error_body_without_a_breach_has_no_code():
    body = password_breach.error_body("password", ValidationError("too short", code="password_too_short"))
    assert body == {"password": ["too short"]}
