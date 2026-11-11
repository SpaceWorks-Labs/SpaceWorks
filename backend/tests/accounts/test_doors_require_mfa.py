"""S-B: every sign-in door makes a person MFA is mandatory for prove their factor (#62).

Staff signing in with Google, Apple, GitHub or an OIDC provider still enter the
authenticator; provider proof stands in for local two-step sign-in for members only.
"""

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.mfa_crypto import totp
from apps.accounts.models import DeviceGrant, User
from apps.accounts.models_social import PlatformSocialAuthSettings
from tests.accounts.account_factories import grant_staff_role
from tests.accounts.mfa_helpers import enrolled
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db
ORIGIN = "http://localhost:5173"


@pytest.fixture(autouse=True)
def _clean(settings):
    settings.AUTH_COOKIE_SECURE = False
    cache.clear()


def _person(username="door-person", *, staff=True, factor=True):
    user = User.objects.create_user(username=username, email=f"{username}@example.test", password="door-pass-123!",
                                    email_verified_at=timezone.now())
    if staff:
        grant_staff_role(user, make_space(f"{username}-space"), role_slug="inventory_manager")
    secret = enrolled(user)[1] if factor else None
    return user, secret


def _code(secret):
    return totp(secret, int(timezone.now().timestamp() // 30))


def _verify(challenge, secret, **headers):
    return APIClient().post("/api/v1/auth/mfa/verify", {"challenge": challenge, "code": _code(secret)},
                            format="json", **headers)


def _mock_social(monkeypatch, user, sub="door-sub"):
    monkeypatch.setattr("apps.accounts.views_social._verify", lambda *a, **k: {
        "sub": sub, "email": user.email, "email_verified": True, "name": user.username})


def _social_web(provider):
    row = PlatformSocialAuthSettings.load()
    row.google_web_client_id = "google-web-client"
    row.apple_service_id = "org.spaceworks.web"
    row.save()
    nonce = APIClient().post("/api/v1/auth/social/nonce", {"provider": provider, "surface": "member",
                             "delivery": "web", "client_platform": "web"}, format="json", HTTP_ORIGIN=ORIGIN)
    assert nonce.status_code == 200, nonce.data
    return APIClient().post(f"/api/v1/auth/social/{provider}", {
        "id_token": "provider-token", "nonce": nonce.data["nonce"], "surface": "member", "delivery": "web",
        "client_platform": "web"}, format="json", HTTP_ORIGIN=ORIGIN)


def test_password_door_challenges_a_required_staff_user():
    user, secret = _person()
    response = APIClient().post("/api/v1/auth/login", {"username": user.username, "password": "door-pass-123!"},
                                format="json", HTTP_ORIGIN=ORIGIN)
    assert response.status_code == 200, response.data
    assert response.data["mfa_required"] is True and response.data["purpose"] == "login"
    assert response.data["factors"] == ["totp"] and "access" not in response.data
    done = _verify(response.data["challenge"], secret, HTTP_ORIGIN=ORIGIN)
    assert done.status_code == 200, done.data
    claims = AccessToken(done.data["access"])
    assert claims["mfa_source"] == "verified" and claims["mfa_method"] == "totp"


@pytest.mark.parametrize("provider", ["google", "apple"])
def test_google_and_apple_web_challenge_staff_then_verify(monkeypatch, provider):
    user, secret = _person(f"door-{provider}")
    _mock_social(monkeypatch, user)
    response = _social_web(provider)
    assert response.status_code == 200, response.data
    assert response.data["mfa_required"] is True and "access" not in response.data
    assert "refresh_token" not in response.cookies
    done = _verify(response.data["challenge"], secret, HTTP_ORIGIN=ORIGIN)
    assert done.status_code == 200, done.data
    assert AccessToken(done.data["access"])["mfa_source"] == "verified"


@pytest.mark.parametrize("provider", ["google", "apple"])
def test_members_keep_provider_proof_on_social_doors(monkeypatch, provider):
    user, _secret = _person(f"door-member-{provider}", staff=False)
    _mock_social(monkeypatch, user)
    response = _social_web(provider)
    assert response.status_code == 200, response.data
    assert "challenge" not in response.data
    assert AccessToken(response.data["access"])["mfa_source"] == "provider"


def test_provider_proof_never_satisfies_a_required_user_without_a_factor(monkeypatch):
    user, _ = _person("door-unenrolled", factor=False)
    _mock_social(monkeypatch, user)
    response = _social_web("google")
    assert response.status_code == 200, response.data
    assert "challenge" not in response.data  # the grace: member features keep working (#128 C-1)
    assert AccessToken(response.data["access"])["mfa_source"] == "none"


def test_google_device_challenges_staff_and_finishes_with_the_grant(monkeypatch, settings):
    from tests.accounts.test_social_first_grant import (
        complete_login, configure_native_social, issue_challenge, mock_attestation, request_nonce,
    )
    configure_native_social(settings)
    user, secret = _person("door-device")
    challenge = issue_challenge(APIClient())
    nonce = request_nonce(APIClient(), challenge)
    _mock_social(monkeypatch, user)
    mock_attestation(monkeypatch, challenge)
    response = complete_login(APIClient(), nonce.data["nonce"], challenge)
    assert response.status_code == 200, response.data
    assert response.data["mfa_required"] is True and response.data["factors"] == ["totp"]
    assert not DeviceGrant.objects.filter(user=user).exists()
    done = _verify(response.data["challenge"], secret)
    assert done.status_code == 200, done.data
    assert DeviceGrant.objects.get(user=user).login_method == "social"
    assert done.data["device_trust"]


def test_github_challenges_staff(monkeypatch, settings):
    from tests.accounts import test_github_auth as gh
    user, secret = _person("door-github")
    user.email = "primary@example.test"
    user.save(update_fields=["email"])
    gh.link(user)  # staff are never auto-linked by email: the identity is already theirs
    settings.CORS_ALLOWED_ORIGINS = [gh.ORIGIN]
    row = PlatformSocialAuthSettings.load()
    row.github_client_id = "github-oauth-client"
    row.set_github_client_secret(gh.SECRET)
    row.save()
    _github(monkeypatch, gh)
    response = gh.callback(gh.start())
    assert response.status_code == 200, response.data
    assert response.data["mfa_required"] is True and "refresh_token" not in response.cookies
    done = _verify(response.data["challenge"], secret, HTTP_ORIGIN=gh.ORIGIN)
    assert done.status_code == 200, done.data
    assert AccessToken(done.data["access"])["mfa_source"] == "verified"


def _github(monkeypatch, gh):
    def post(url, **kwargs):
        return gh.JsonResponse({"access_token": gh.TOKEN, "token_type": "bearer"})

    def get(url, **kwargs):
        if url == "https://api.github.com/user":
            return gh.JsonResponse({"id": 1234567, "name": "GitHub Staff"})
        return gh.JsonResponse([{"email": "primary@example.test", "primary": True, "verified": True}])

    monkeypatch.setattr("apps.accounts.github_http.requests.post", post)
    monkeypatch.setattr("apps.accounts.github_http.requests.get", get)


def test_oidc_browser_challenges_staff(monkeypatch, settings):
    from tests.accounts.oidc_browser_helpers import ORIGIN as OIDC_ORIGIN, make_provider, metadata, start
    settings.CORS_ALLOWED_ORIGINS = [OIDC_ORIGIN]
    user, secret = _person("door-oidc")
    provider = make_provider()
    monkeypatch.setattr("apps.accounts.views_oidc_browser.discover", lambda _: metadata(provider))
    monkeypatch.setattr("apps.accounts.views_oidc_browser.exchange_code", lambda *a, **k: "id-token")
    monkeypatch.setattr("apps.accounts.views_oidc_browser.verify_oidc_token",
                        lambda *a, **k: {"sub": "oidc-sub", "email": user.email, "email_verified": True})
    started = start(APIClient())
    response = APIClient().post("/api/v1/auth/social/oidc/callback", {
        "code": "code", "state": started.data["state"], "nonce": started.data["nonce"]},
        format="json", HTTP_ORIGIN=OIDC_ORIGIN)
    assert response.status_code == 200, response.data
    assert response.data["mfa_required"] is True
    done = _verify(response.data["challenge"], secret, HTTP_ORIGIN=OIDC_ORIGIN)
    assert done.status_code == 200, done.data


def test_phone_web_challenges_an_enrolled_staff_user(monkeypatch):
    user, secret = _person("door-phone")
    monkeypatch.setattr("apps.accounts.views_phone._phone_login_available", lambda: True)
    monkeypatch.setattr("apps.accounts.views_phone.confirm_login", lambda phone, code: user)
    response = APIClient().post("/api/v1/auth/phone/login/confirm", {"phone": "+15550000001", "code": "123456"},
                                format="json", HTTP_ORIGIN=ORIGIN)
    assert response.status_code == 200, response.data
    assert response.data["mfa_required"] is True
    done = _verify(response.data["challenge"], secret, HTTP_ORIGIN=ORIGIN)
    assert done.status_code == 200, done.data
