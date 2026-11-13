"""POST /auth/social/oidc/<slug> reaches its handler (SWITCH-MATRIX regression).

The handler took only `request`, so the route's `slug` kwarg raised TypeError and every OIDC ID-token sign-in
answered 500. Now: a bad or missing body is a typed 400, an unconfigured provider is the typed 404
`social_unavailable`, the platform social switch off is the same 404, and a verified token signs the member in.
"""

import pytest
from rest_framework.test import APIClient

from apps.accounts import views_social_login as view
from apps.accounts.models import User
from tests.accounts.oidc_browser_helpers import make_provider

pytestmark = pytest.mark.django_db

URL = "/api/v1/auth/social/oidc/campus"
BODY = {"id_token": "t", "nonce": "n" * 32, "surface": "member", "delivery": "web", "client_platform": "web"}


def test_a_missing_body_is_a_typed_400_not_a_500():
    response = APIClient(raise_request_exception=False).post(URL, {}, format="json")
    assert response.status_code == 400
    assert {"id_token", "nonce"} <= set(response.data)


def test_an_invalid_surface_is_a_400_naming_the_field():
    response = APIClient(raise_request_exception=False).post(URL, {**BODY, "surface": "root"}, format="json")
    assert response.status_code == 400 and "surface" in response.data


def test_an_unconfigured_provider_is_the_typed_404_social_unavailable():
    response = APIClient(raise_request_exception=False).post(URL, BODY, format="json")
    assert (response.status_code, response.data["code"]) == (404, "social_unavailable")


def test_a_verified_token_signs_the_member_in_through_the_slug_route(monkeypatch):
    make_provider(slug="campus")
    user = User.objects.create_user(username="oidc-route-member", email="oidc-route@example.test",
                                    access_status=User.AccessStatus.ACTIVE)
    monkeypatch.setattr(view, "social_login_enabled", lambda: True)
    monkeypatch.setattr(view, "provider_settings", lambda provider, platform: ({}, "audience"))
    monkeypatch.setattr(view, "consume_social_nonce", lambda *a, **k: (None, None))
    monkeypatch.setattr("apps.accounts.views_social._verify", lambda provider, token, nonce, audience: {"sub": "s-1"})
    monkeypatch.setattr(view, "resolve_social_identity", lambda **k: (user, "login"))
    response = APIClient(raise_request_exception=False).post(URL, BODY, format="json")
    assert response.status_code == 200, getattr(response, "data", None)
    assert response.data["outcome"] == "login" and response.data["user"]["username"] == "oidc-route-member"
    assert response.data["access"]
