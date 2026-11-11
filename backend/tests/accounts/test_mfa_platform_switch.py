"""Deployment MFA policy must survive switch changes and refresh rotation."""

import pytest
from cryptography.fernet import Fernet
from django.test import Client
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import UntypedToken

from apps.accounts import mfa_policy
from apps.accounts.mfa_crypto import totp
from apps.accounts.mfa_recovery import reset_superadmin_mfa
from apps.accounts.models import PlatformLoginMethods, User
from apps.accounts.models_mfa import MFAChallenge
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from tests.accounts.mfa_helpers import enrolled
from tests.accounts.test_device_auth import attested_login

pytestmark = pytest.mark.django_db
PASSWORD = "Platform MFA password 284!"
OFF_MESSAGE = "Two-step sign-in is turned off on this deployment."
ORIGIN = "http://localhost:5000"


@pytest.fixture(autouse=True)
def encryption(settings):
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode()
    settings.CORS_ALLOWED_ORIGINS = [ORIGIN]


def switch(enabled):
    PlatformLoginMethods.objects.update_or_create(pk=1, defaults={"mfa_enabled": enabled})


def person():
    return User.objects.create_user(username="switch-user", password=PASSWORD)


def require_staff(user):
    space = Makerspace.objects.create(name="Required MFA", slug="switch-required")
    # Provider/device subjects remain member accounts with delegated staff authority.
    # A Member cannot receive a built-in staff role after the account split.
    from apps.accounts.rbac import Action
    from apps.organizations.models import Organization, OrganizationMakerspace, OrganizationMembership
    organization = Organization.objects.create(name="MFA policy org", slug="mfa-policy-org")
    OrganizationMakerspace.objects.create(organization=organization, makerspace=space, relationship="owner")
    OrganizationMembership.objects.create(organization=organization, user=user,
                                          granted_actions=[Action.VIEW_INVENTORY])


def password_login(client, user):
    return client.post("/api/v1/auth/login", {"username": user.username, "password": PASSWORD,
                       "surface": "member"}, format="json")


def web_refresh(client):
    return client.post("/api/v1/auth/refresh", HTTP_X_REFRESH_CSRF="1", HTTP_ORIGIN=ORIGIN)


@pytest.mark.parametrize("enroll", [False, True])
def test_off_never_pauses_staff_mfa(enroll):
    """S-A (#62): the platform switch governs member opt-in only."""
    user, client = person(), APIClient()
    require_staff(user)
    if enroll:
        enrolled(user)
    switch(False)
    assert mfa_policy.required(user) and mfa_policy.available(user)
    assert mfa_policy.needs_challenge(user) is enroll
    response = password_login(client, user)
    assert response.status_code == 200
    if enroll:
        assert response.data["mfa_required"]
        return
    assert UntypedToken(response.data["access"])["mfa_source"] == "none"
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    assert client.get("/api/v1/auth/mfa").data == {
        "available": True, "enabled": False, "required": True, "password_available": True,
    }


def test_off_still_pauses_member_mfa():
    user, client = person(), APIClient()
    enrolled(user)
    switch(False)
    assert not mfa_policy.required(user) and not mfa_policy.needs_challenge(user)
    response = password_login(client, user)
    assert response.status_code == 200 and "challenge" not in response.data
    assert UntypedToken(response.data["access"])["mfa_source"] == "bypass"
    switch(True)
    assert password_login(client, user).data["mfa_required"]


def test_off_refuses_management_and_challenges_created_before_switch_change():
    user, client = person(), APIClient()
    row, secret = enrolled(user)
    raw = password_login(client, user).data["challenge"]
    switch(False)
    signed_in = password_login(client, user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {signed_in.data['access']}")
    for path in ("/api/v1/auth/mfa", "/api/v1/auth/mfa/recovery"):
        response = client.post(path, {"password": PASSWORD}, format="json")
        assert response.status_code == 403 and str(response.data["detail"]) == OFF_MESSAGE
    client.credentials()
    for suffix in ("enroll", "confirm", "verify"):
        response = client.post(f"/api/v1/auth/mfa/{suffix}", {
            "challenge": raw, "code": totp(secret, int(timezone.now().timestamp() // 30)),
        }, format="json")
        assert response.status_code == 403 and str(response.data["detail"]) == OFF_MESSAGE
    assert MFAChallenge.objects.get().consumed_at is None
    row.refresh_from_db()
    assert row.last_step == -1
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {signed_in.data['access']}")
    assert client.post("/api/v1/auth/mfa/disable", {"password": PASSWORD}, format="json").status_code == 200


def test_bypass_web_and_rotated_device_sessions_are_refused_after_reenable(settings, monkeypatch):
    # A member's paused authenticator (staff MFA is never paused, so no staff bypass exists).
    user, web, device = person(), APIClient(), APIClient()
    enrolled(user)
    switch(False)
    signed_in = password_login(web, user)
    assert signed_in.status_code == 200
    # Web rotation must preserve bypass too.
    replacement = web_refresh(web)
    assert replacement.status_code == 200
    assert UntypedToken(replacement.data["access"])["mfa_source"] == "bypass"
    native, _ = attested_login(device, user, settings, monkeypatch, password=PASSWORD)
    assert native.status_code == 200 and "challenge" not in native.data
    rotated = device.post("/api/v1/auth/device/refresh", {"refresh": native.data["refresh"]}, format="json")
    assert rotated.status_code == 200
    assert UntypedToken(rotated.data["refresh"])["mfa_source"] == "bypass"
    switch(True)
    for client, access in ((web, signed_in.data["access"]), (device, rotated.data["access"])):
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        assert client.get("/api/v1/auth/me").status_code == 401
        client.credentials()
    assert web_refresh(web).status_code == 401
    assert device.post("/api/v1/auth/device/refresh", {
        "refresh": rotated.data["refresh"]}, format="json").status_code == 401


def test_enrolled_control_bypass_requires_verification_after_reenable():
    root = User.objects.create_superuser(username="switch-control", password=PASSWORD)
    row, secret = enrolled(root)
    switch(False)
    client = Client()
    assert client.login(username=root.username, password=PASSWORD)
    assert client.session["mfa_source"] == "bypass"
    assert client.session["mfa_version"] == str(row.version)
    assert client.get("/control/").status_code == 200
    assert client.get("/mfa/control/").url == "/control/"
    switch(True)
    assert client.get("/control/").url == "/mfa/control/"
    assert client.get("/mfa/control/").status_code == 200
    assert client.post("/mfa/control/", {
        "code": totp(secret, int(timezone.now().timestamp() // 30)),
    }).url == "/control/"
    assert client.session["mfa_source"] == "verified"
    assert client.get("/control/").status_code == 200


def test_host_reset_revokes_password_only_control_session_until_fresh_login():
    root = User.objects.create_superuser(username="reset-control", password=PASSWORD)
    client = Client()
    client.force_login(root)
    assert client.session["mfa_source"] == "none"
    assert client.get("/control/").status_code == 200
    reset_superadmin_mfa(root)
    response = client.get("/control/", follow=True)
    assert response.redirect_chain[0][0] == "/mfa/control/"
    assert "_auth_user_id" not in client.session
    assert client.login(username=root.username, password=PASSWORD)
    assert client.get("/control/").status_code == 200


def test_host_reset_revokes_control_session_even_while_switch_off():
    switch(False)
    root = User.objects.create_superuser(username="off-reset-root", password=PASSWORD)
    enrolled(root)
    client = Client()
    client.force_login(root)  # stamps the current credential version
    assert client.get("/control/").status_code == 200
    reset_superadmin_mfa(root)
    assert client.get("/control/").url == "/mfa/control/"
    assert client.get("/mfa/control/").url == "/control/login/"
    assert "_auth_user_id" not in client.session


def test_enrolled_account_refuses_a_token_without_verified_proof():
    from apps.accounts.tokens import SpaceWorksRefreshToken
    user = person()
    row, _ = enrolled(user)
    mfa_policy.stamp(user, row)
    refresh = SpaceWorksRefreshToken.for_user(user)
    assert refresh["mfa_source"] == mfa_policy.VERIFIED
    refresh["mfa_source"] = mfa_policy.NONE  # e.g. minted while the switch flipped on
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    assert client.get("/api/v1/auth/me").status_code == 401
