"""Global sign-out invalidates browser/native credentials together, without tenant gates."""

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

from apps.accounts.models import DeviceGrant
from apps.accounts.tokens import SpaceWorksRefreshToken
from apps.accounts.web_sessions import active_sessions, legacy_sessions
from apps.audit.models import AuditLog
from apps.integrations.models import PushDevice
from apps.makerspaces.models import MakerspaceMembership
from tests.accounts.test_device_auth import attested_login
from tests.accounts.native_helpers_m1d import attested_staff_login
from tests.accounts.account_factories import make_staff, make_membership
from tests.accounts.test_password_login_surfaces_p3ii import _bearer
from tests.return_helpers import make_member, make_space, make_user
from tests.test_auth import _csrf_headers, _login

pytestmark = pytest.mark.django_db
URL = "/api/v1/auth/logout-all"
PASSWORD = "strong-device-password"


def web_login(user, settings):
    client = APIClient()
    response = client.post("/api/v1/auth/login", {
        "username": user.username, "password": PASSWORD,
    }, format="json")
    assert response.status_code == 200
    refresh = response.cookies[settings.AUTH_REFRESH_COOKIE].value
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    return client, response.data["access"], refresh


@pytest.mark.parametrize("caller", ["web", "device"])
@pytest.mark.parametrize("account_only", [False, True])
def test_logout_all_revokes_every_credential_and_push(caller, account_only, settings, monkeypatch):
    settings.CORS_ALLOWED_ORIGINS = ["http://localhost:5000"]
    user = make_user("logout-all-owner", password=PASSWORD, access_status="active")
    browsers = [web_login(user, settings), web_login(user, settings)]
    native = []
    for _ in range(2):
        login, _ = attested_login(APIClient(), user, settings, monkeypatch)
        assert login.status_code == 200
        native.append(login.data)
    # Make the push tenant after device login: account-only sign-in also works
    # before any makerspace exists. No membership is needed to sign out.
    space = make_space("logout-all-push")
    if not account_only:
        make_membership(user, space)
    for index, login in enumerate(native):
        device = PushDevice(
            user=user, makerspace=space, device_grant_id=login["device_grant"]["id"],
            provider="apns", environment="development", token_fingerprint=str(index) * 64,
        )
        device.set_token(f"push-secret-{index}")
        device.save()
    legacy = SpaceWorksRefreshToken.for_user(user, web_session=False)
    # Turn off optional identity/mobile capabilities after issuance. Sign-out
    # must remain reachable even when those features can no longer mint logins.
    space.enabled_modules = [key for key in space.enabled_modules
                             if key not in {"membership", "member_accounts", "mobile"}]
    space.save(update_fields=["enabled_modules"])
    foreign = APIClient()
    foreign_login = _login(foreign, username="logout-all-other")
    assert foreign_login.status_code == 200
    foreign_access = foreign_login.data["access"]
    foreign_refresh = foreign_login.cookies[settings.AUTH_REFRESH_COOKIE].value

    client = browsers[0][0] if caller == "web" else _bearer(native[0]["access"])
    response = client.post(URL)

    assert response.status_code == 200
    assert response.data == {"web_sessions": 3, "devices": 2}
    cookie = response.cookies[settings.AUTH_REFRESH_COOKIE]
    assert cookie.value == "" and cookie["max-age"] == 0
    assert cookie["path"] == settings.AUTH_COOKIE_PATH
    assert not active_sessions(user).exists()
    assert not list(legacy_sessions(user))
    assert not DeviceGrant.objects.filter(user=user, status="active").exists()
    assert not DeviceGrant.objects.filter(user=user, revoked_at__isnull=True).exists()
    assert not PushDevice.objects.filter(user=user, active=True).exists()
    assert not PushDevice.objects.filter(user=user, invalidated_at__isnull=True).exists()
    assert not OutstandingToken.objects.filter(user=user, blacklistedtoken__isnull=True).exists()
    for _, access, refresh in browsers:
        assert _bearer(access).get("/api/v1/auth/me").status_code == 401
        fresh = APIClient()
        fresh.cookies[settings.AUTH_REFRESH_COOKIE] = refresh
        assert fresh.post("/api/v1/auth/refresh", **_csrf_headers()).status_code == 401
    fresh = APIClient()
    fresh.cookies[settings.AUTH_REFRESH_COOKIE] = str(legacy)
    assert fresh.post("/api/v1/auth/refresh", **_csrf_headers()).status_code == 401
    for login in native:
        assert _bearer(login["access"]).get("/api/v1/auth/me").status_code == 401
        assert APIClient().post("/api/v1/auth/device/refresh", {
            "refresh": login["refresh"],
        }, format="json").status_code == 401
    event = AuditLog.objects.get(action="auth.logout_all", actor=user)
    assert event.makerspace_id is None and event.target_id == str(user.pk)
    assert event.meta == {"web_sessions": 2, "legacy_sessions": 1,
                          "devices": 2, "refresh_tokens": 5}
    assert _bearer(foreign_access).get("/api/v1/auth/me").status_code == 200
    foreign.cookies[settings.AUTH_REFRESH_COOKIE] = foreign_refresh
    assert foreign.post("/api/v1/auth/refresh", **_csrf_headers()).status_code == 200
    if account_only:
        assert not MakerspaceMembership.objects.filter(user=user).exists()


def test_logout_all_requires_authentication():
    assert APIClient().post(URL).status_code == 401
    assert not AuditLog.objects.filter(action="auth.logout_all").exists()


def test_native_staff_can_logout_all_without_selected_makerspace(settings, monkeypatch):
    space = make_space("logout-all-staff")
    space.enabled_modules = sorted(set(space.enabled_modules) | {"mobile"})
    space.save(update_fields=["enabled_modules"])
    user = make_staff(space, username="logout-all-staff", role_slug="inventory_manager", password=PASSWORD)
    login, _ = attested_staff_login(APIClient(), user, settings, monkeypatch)
    assert login.status_code == 200
    assert DeviceGrant.objects.get(pk=login.data["device_grant"]["id"]).authority == "staff"
    response = _bearer(login.data["access"]).post(URL)
    assert response.status_code == 200
    assert response.data == {"web_sessions": 0, "devices": 1}


def test_unverified_account_can_logout_all(settings):
    user = make_user("logout-all-unverified", password=PASSWORD, access_status="active",
                     self_registered_at=timezone.now())
    client, access, _ = web_login(user, settings)
    response = client.post(URL)
    assert response.status_code == 200
    assert response.data == {"web_sessions": 1, "devices": 0}
    assert _bearer(access).get("/api/v1/auth/me").status_code == 401


def test_logout_all_rolls_back_when_audit_fails(settings, monkeypatch):
    user = make_user("logout-all-rollback", password=PASSWORD, access_status="active")
    client, access, _ = web_login(user, settings)
    login, _ = attested_login(APIClient(), user, settings, monkeypatch)
    assert login.status_code == 200

    def fail_audit(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr("apps.accounts.views_logout_all.audit_events.record_auth_event", fail_audit)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        client.post(URL)
    assert _bearer(access).get("/api/v1/auth/me").status_code == 200
    assert _bearer(login.data["access"]).get("/api/v1/auth/me").status_code == 200
    assert not OutstandingToken.objects.filter(user=user, blacklistedtoken__isnull=False).exists()
