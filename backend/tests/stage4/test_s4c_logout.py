"""Logout clears one explicit cookie even when its credential is already unusable."""

from datetime import timedelta

import pytest
from django.conf import settings
from django.contrib.sessions.models import Session
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken

from apps.accounts.credential_revocation import revoke_sessions_only
from apps.accounts.session_context import cookie_name
from apps.accounts.tokens import SpaceWorksRefreshToken
from apps.accounts.web_sessions import revoke_session
from apps.accounts.models import User
from .test_s4c_refresh_revocation import device_tokens

pytestmark = pytest.mark.django_db
# Decisions 63/66 (U-B, one account per person): only the person and platform cookies exist.
CONTEXTS = ["person", "platform"]
HEADERS = {"HTTP_ORIGIN": "http://localhost:5000", "HTTP_X_REFRESH_CSRF": "1"}
LOGOUT = "/api/v1/auth/logout"
ORIGIN = "http://localhost:5000"


@pytest.fixture
def principals(settings):
    settings.CORS_ALLOWED_ORIGINS = [ORIGIN]
    settings.PLATFORM_STAFF_ORIGINS = [ORIGIN]
    person = User.objects.create_user("person", email="person@example.test", password="Logout password 965!")
    platform = User.objects.create_superuser("platform", email="platform@example.test", password="Logout password 965!")
    return person, platform


@pytest.mark.parametrize("index", range(2))
@pytest.mark.parametrize("state", ["live", "missing", "malformed", "expired", "blacklisted", "revoked", "session_revoked"])
def test_logout_always_clears_only_the_selected_context(principals, index, state):
    client = APIClient()
    tokens = [SpaceWorksRefreshToken.for_user(user) for user in principals]
    for context, token in zip(CONTEXTS, tokens):
        client.cookies[cookie_name(context)] = str(token)
    selected = tokens[index]
    if state == "missing":
        del client.cookies[cookie_name(CONTEXTS[index])]
    elif state == "malformed":
        client.cookies[cookie_name(CONTEXTS[index])] = "invalid.refresh.cookie"
    elif state == "expired":
        selected.set_exp(lifetime=timedelta(seconds=-10))
        client.cookies[cookie_name(CONTEXTS[index])] = str(selected)
    elif state == "blacklisted":
        selected.blacklist()
    elif state == "revoked":
        revoke_sessions_only(principals[index], reason="s4c.logout")
    elif state == "session_revoked":
        revoke_session(principals[index], selected["sid"])
    other_cookies = {cookie_name(context): client.cookies[cookie_name(context)].value
                     for context in CONTEXTS if context != CONTEXTS[index]}
    response = client.post(LOGOUT, {"context": CONTEXTS[index]}, format="json", **HEADERS)
    assert response.status_code == 204, response.data
    name = cookie_name(CONTEXTS[index])
    assert set(response.cookies) == {name}
    assert response.cookies[name].value == ""
    assert response.cookies[name]["max-age"] == 0
    assert response.cookies[name]["path"] == settings.AUTH_COOKIE_PATH
    assert all(client.cookies[key].value == value for key, value in other_cookies.items())
    for i, token in enumerate(tokens):
        if i != index:
            assert str(SpaceWorksRefreshToken(str(token))) == str(token)
    if state == "live":
        assert BlacklistedToken.objects.filter(token__jti=selected["jti"]).exists()
        assert BlacklistedToken.objects.filter(token__jti=selected["sid"]).exists()


@pytest.mark.parametrize("index", range(2))
@pytest.mark.parametrize("headers", [{}, {"HTTP_ORIGIN": HEADERS["HTTP_ORIGIN"]},
    {"HTTP_X_REFRESH_CSRF": "1", "HTTP_ORIGIN": "https://attacker.example.test"}])
def test_invalid_cookie_does_not_bypass_csrf(principals, index, headers):
    client = APIClient()
    name = cookie_name(CONTEXTS[index])
    client.cookies[name] = "already.invalid"
    response = client.post(LOGOUT, {"context": CONTEXTS[index]}, format="json", **headers)
    assert response.status_code == 403
    assert not response.cookies
    assert client.cookies[name].value == "already.invalid"


def test_invalid_member_cookie_keeps_member_origin_policy(principals, monkeypatch):
    monkeypatch.setattr("apps.accounts.auth_cookies.member_origin_is_registered", lambda _: False)
    monkeypatch.setattr("apps.accounts.auth_cookies.staff_origin_is_registered", lambda _: True)
    client = APIClient()
    client.cookies["refresh_token"] = "invalid"
    response = client.post(LOGOUT, {}, format="json", **HEADERS)
    assert response.status_code == 403
    assert not response.cookies


def test_wrong_context_is_refused_and_cleared_without_consuming_other_token(principals):
    member = SpaceWorksRefreshToken.for_user(principals[0])
    client = APIClient()
    client.cookies["refresh_token"] = str(member)
    client.cookies[cookie_name(CONTEXTS[1])] = str(member)
    response = client.post(LOGOUT, {"context": CONTEXTS[1]}, format="json", **HEADERS)
    assert response.status_code == 401
    assert set(response.cookies) == {cookie_name(CONTEXTS[1])}
    assert response.cookies[cookie_name(CONTEXTS[1])].value == ""
    assert client.cookies["refresh_token"].value == str(member)
    assert not BlacklistedToken.objects.filter(token__jti=member["jti"]).exists()
    assert not BlacklistedToken.objects.filter(token__jti=member["sid"]).exists()


def test_default_context_does_not_select_the_platform_cookie(principals):
    client = APIClient()
    raw = str(SpaceWorksRefreshToken.for_user(principals[1]))
    client.cookies[cookie_name(CONTEXTS[1])] = raw
    response = client.post(LOGOUT, {}, format="json", **HEADERS)
    assert response.status_code == 204
    assert set(response.cookies) == {"refresh_token"}
    assert client.cookies[cookie_name(CONTEXTS[1])].value == raw
    assert str(SpaceWorksRefreshToken(raw)) == raw


def test_invalid_context_cannot_choose_a_cookie_to_clear(principals):
    response = APIClient().post(LOGOUT, {"context": "staff:../../platform"}, format="json", **HEADERS)
    assert response.status_code == 400
    assert not response.cookies


def test_device_logout_ignores_refresh_validity_and_keeps_browser_sessions(principals):
    user = principals[0]
    raw = device_tokens(user)
    refresh = SpaceWorksRefreshToken(raw)
    browser = SpaceWorksRefreshToken.for_user(user)
    refresh.blacklist()
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    response = client.post("/api/v1/auth/device/logout")
    assert response.status_code == 200, response.data
    assert not response.cookies
    assert not user.device_grants.filter(status="active").exists()
    assert not user.device_refresh_families.filter(revoked_at__isnull=True).exists()
    assert str(SpaceWorksRefreshToken(str(browser))) == str(browser)


@pytest.mark.parametrize("expired_session", [False, True])
def test_control_logout_flushes_only_django_session(principals, expired_session):
    client = APIClient()
    client.force_login(principals[1])
    session_key = client.session.session_key
    raws = {cookie_name(context): str(SpaceWorksRefreshToken.for_user(user))
            for context, user in zip(CONTEXTS, principals)}
    for name, raw in raws.items():
        client.cookies[name] = raw
    if expired_session:
        Session.objects.filter(session_key=session_key).delete()
    response = client.post("/control/logout/")
    assert response.status_code in {200, 302}
    assert not Session.objects.filter(session_key=session_key).exists()
    assert not (set(response.cookies) & set(raws))
    assert all(client.cookies[name].value == raw for name, raw in raws.items())
    for raw in raws.values():
        SpaceWorksRefreshToken(raw)
