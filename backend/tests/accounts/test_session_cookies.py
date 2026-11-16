"""U-A2: two refresh cookies (person, platform); logout expires the release-1 staff cookies."""

import pytest
from django.conf import settings as django_settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.makerspaces.models import Makerspace
from tests.accounts.account_factories import make_staff

pytestmark = pytest.mark.django_db
ORIGIN = "http://localhost:5000"
PASSWORD = "Strong-Cookie-Pass-17"


def browser():
    client = APIClient()
    client.credentials(HTTP_ORIGIN=ORIGIN, **{"HTTP_" + django_settings.AUTH_REFRESH_CSRF_HEADER.upper().replace("-", "_"): "1"})
    return client


def test_staff_person_uses_the_person_cookie_and_refreshes():
    space = Makerspace.objects.create(name="Cookie", slug="cookie-space")
    make_staff(space, username="cookie-staff", password=PASSWORD)
    client = browser()
    login = client.post("/api/v1/auth/login", {"username": "cookie-staff", "password": PASSWORD}, format="json")
    assert login.status_code == 200, login.data
    assert django_settings.AUTH_REFRESH_COOKIE in login.cookies
    assert not any(name.startswith("refresh_token_staff_") for name in login.cookies)
    # `member` and `staff:<slug>` are release-1 aliases of person, accepted for one release.
    for retired in ({"context": "member"}, {"context": "staff:cookie-space"}):  # removed by U-B (#162(4))
        assert client.post("/api/v1/auth/refresh", retired, format="json").status_code == 400
    for context in ({}, {"context": "person"}):
        refreshed = client.post("/api/v1/auth/refresh", context, format="json")
        assert refreshed.status_code == 200, refreshed.data
        assert refreshed.data["user"]["staff_roles"]
    assert client.post("/api/v1/auth/refresh", {"context": "bogus"}, format="json").status_code == 400


def test_logout_expires_legacy_staff_cookies():
    User.objects.create_user("cookie-person", password=PASSWORD)
    client = browser()
    assert client.post("/api/v1/auth/login", {"username": "cookie-person", "password": PASSWORD},
                       format="json").status_code == 200
    client.cookies["refresh_token_staff_old-space"] = "stale"
    client.cookies["refresh_token_staff_other"] = "stale"
    response = client.post("/api/v1/auth/logout", {}, format="json")
    assert response.status_code == 204
    for name in (django_settings.AUTH_REFRESH_COOKIE, "refresh_token_staff_old-space", "refresh_token_staff_other"):
        assert response.cookies[name]["max-age"] == 0, name


def test_platform_cookie_is_separate():
    User.objects.create_superuser("cookie-root", email="root@cookie.test", password=PASSWORD)
    client = browser()
    login = client.post("/api/v1/auth/login", {"username": "cookie-root", "password": PASSWORD}, format="json")
    assert login.status_code == 200, login.data
    assert "refresh_token_platform" in login.cookies
    assert client.post("/api/v1/auth/refresh", {"context": "platform"}, format="json").status_code == 200
