"""Candidate tests; no session is validated, rotated or persisted."""
import pytest
from django.conf import settings
from rest_framework.test import APIRequestFactory

from apps.accounts.views_browser_state import BrowserStateView


def get(*, cookies=None, origin="http://testserver", authorization=None, fetch_site="same-origin"):
    headers = {"HTTP_ORIGIN": origin, "HTTP_SEC_FETCH_SITE": fetch_site}
    if authorization is not None:
        headers["HTTP_AUTHORIZATION"] = authorization
    request = APIRequestFactory().get("/api/v1/auth/browser-state", **headers)
    request.COOKIES.update(cookies or {})
    return BrowserStateView.as_view()(request)


def test_no_credentials_is_anonymous_and_not_cacheable():
    response = get()
    assert response.status_code == 200
    assert response.data == {"state": "anonymous"}
    assert response["Cache-Control"] == "no-store"
    assert {"cookie", "authorization", "origin"} <= {s.strip().lower() for s in response["Vary"].split(",")}
    assert "Set-Cookie" not in response


@pytest.mark.parametrize("name", [settings.AUTH_REFRESH_COOKIE, "refresh_token_platform", "refresh_token_staff_old", settings.SESSION_COOKIE_NAME])
def test_any_cookie_name_even_empty_means_auth_present(name):
    assert get(cookies={name: ""}).data == {"state": "auth_present"}


def test_any_authorization_even_invalid_means_auth_present():
    assert get(authorization="Bearer invalid").data == {"state": "auth_present"}
    assert get(authorization="").data == {"state": "auth_present"}


@pytest.mark.django_db  # an unknown origin is checked against registered member domains
def test_disallowed_origin_fails_closed_with_no_store():
    response = get(origin="https://untrusted.invalid")
    assert response.status_code == 403
    assert response["Cache-Control"] == "no-store"


def test_allowed_cross_origin_is_unknown_not_anonymous(settings):
    settings.CORS_ALLOWED_ORIGINS = ["https://frontend.example"]
    assert get(origin="https://frontend.example", fetch_site="same-site").data == {"state": "unknown"}
    assert get(origin="https://frontend.example", fetch_site="same-site", cookies={settings.AUTH_REFRESH_COOKIE: "x"}).data == {"state": "auth_present"}


def test_proxy_same_browser_origin_uses_trusted_frontend_origin(settings):
    settings.CORS_ALLOWED_ORIGINS = ["http://localhost:5000"]
    response = get(origin="http://localhost:5000", fetch_site="same-origin")
    assert response.data == {"state": "anonymous"}


@pytest.mark.django_db
def test_verified_custom_origin_resolves_through_auth_origin_policy():
    from apps.makerspaces.models import Makerspace
    from tests.return_helpers import make_space
    space = make_space("browser-state-origin")
    space.frontend_domain = "verified.example.test"
    space.frontend_domain_status = Makerspace.DomainStatus.VERIFIED
    space.save(update_fields=["frontend_domain", "frontend_domain_status"])
    assert get(origin="https://verified.example.test", fetch_site="same-origin").data == {"state": "anonymous"}
    assert get(origin="https://verified.example.test", fetch_site="same-site").data == {"state": "unknown"}


def test_missing_browser_fetch_metadata_is_unknown():
    assert get(fetch_site="").data == {"state": "unknown"}


def test_auth_cookie_path_covers_endpoint():
    assert "/api/v1/auth/browser-state".startswith(settings.AUTH_COOKIE_PATH)
