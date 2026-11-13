"""Cookie refresh reports the same effective authority as the replacement JWT."""

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.models import User
from apps.accounts.session_context import cookie_name, token_context
from apps.accounts.tokens import SpaceWorksRefreshToken
from tests.accounts.account_factories import make_staff
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db
ORIGIN = "http://localhost:5000"


@pytest.mark.parametrize("surface", ["member", "staff_person", "platform", "verification_only"])
def test_cookie_refresh_preserves_effective_session_authority(surface, settings):
    settings.CORS_ALLOWED_ORIGINS = [ORIGIN]
    settings.PLATFORM_STAFF_ORIGINS = [ORIGIN]
    if surface == "staff_person":
        # Release 2: a person holding a staff role has an ordinary member session.
        user, surface = make_staff(make_space("refresh-authority"), username="refresh-authority"), "member"
    else:
        user = User.objects.create_user(username="refresh-authority",
            account_kind="platform" if surface == "platform" else "member",
            is_superuser=surface == "platform", role="superadmin" if surface == "platform" else "requester")
    if surface == "verification_only":
        user.self_registered_at = timezone.now()
        user.save(update_fields=["self_registered_at"])
    refresh = SpaceWorksRefreshToken.for_user(user)
    refresh["surface"] = surface
    context = token_context(refresh)
    client = APIClient()
    client.cookies[cookie_name(context)] = str(refresh)

    result = client.post("/api/v1/auth/refresh", {"context": context}, format="json",
                         HTTP_X_REFRESH_CSRF="1", HTTP_ORIGIN=ORIGIN)

    assert result.status_code == 200, result.data
    assert result.data["user"]["session_authority"] == surface
    assert AccessToken(result.data["access"])["surface"] == surface
    assert result.data["user"]["kind"] == ("platform" if surface == "platform" else "person")
    assert result.data["user"]["id"] == user.pk


@pytest.mark.parametrize("retired", ["delegated", "staff_api", "staff"])
def test_release_one_surfaces_are_refused(retired, settings):
    settings.CORS_ALLOWED_ORIGINS = [ORIGIN]
    user = make_staff(make_space("refresh-retired"), username="refresh-retired")
    refresh = SpaceWorksRefreshToken.for_user(user)
    refresh["surface"] = retired
    client = APIClient()
    client.cookies[cookie_name("person")] = str(refresh)
    result = client.post("/api/v1/auth/refresh", {}, format="json", HTTP_X_REFRESH_CSRF="1", HTTP_ORIGIN=ORIGIN)
    assert result.status_code == 401


def test_verified_account_refresh_reports_effective_member_surface(settings):
    settings.CORS_ALLOWED_ORIGINS = [ORIGIN]
    user = User.objects.create_user(username="newly-verified-refresh", self_registered_at=timezone.now())
    refresh = SpaceWorksRefreshToken.for_user(user)
    refresh["surface"] = "verification_only"
    User.objects.filter(pk=user.pk).update(email_verified_at=timezone.now())
    client = APIClient()
    client.cookies[cookie_name("person")] = str(refresh)
    result = client.post("/api/v1/auth/refresh", HTTP_X_REFRESH_CSRF="1", HTTP_ORIGIN=ORIGIN)
    assert result.status_code == 200, result.data
    assert result.data["user"]["session_authority"] == "member"
