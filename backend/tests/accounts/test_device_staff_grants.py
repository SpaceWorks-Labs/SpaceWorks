"""U-A2: a native staff grant is a step-up on a person, fixed to one makerspace (Q12)."""

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.mfa_crypto import totp
from apps.accounts.models import DeviceGrant, User
from apps.accounts.models_mfa import UserMFA
from apps.accounts.services_staff_grants import revoke_staff_grants
from apps.audit.models import AuditLog
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from tests.accounts.account_factories import make_membership, make_staff
from tests.accounts.mfa_helpers import enrolled
from tests.accounts.test_device_auth import configure_apple, mock_apple_provider

pytestmark = pytest.mark.django_db
PASSWORD = "Strong-Device-Pass-42"
CHALLENGE = "/api/v1/auth/device/attestation-challenge"
APP = {"platform": "apple", "app_id": "org.spaceworks.app", "environment": "development"}


@pytest.fixture
def space():
    return Makerspace.objects.create(name="Grant Space", slug="grant-space")


def attestation(client, settings, monkeypatch):
    configure_apple(settings)
    raw = client.post(CHALLENGE, APP, format="json").data["challenge"]
    mock_apple_provider(monkeypatch, raw)
    return {"challenge": raw, "attestation": {"assertion": "opaque"}}


def device_login(client, user, settings, monkeypatch, **extra):
    payload = {**APP, "username": user.username, "password": PASSWORD,
               **attestation(client, settings, monkeypatch), **extra}
    return client.post("/api/v1/auth/device/login", payload, format="json")


def verify(client, response, secret):
    return client.post("/api/v1/auth/mfa/verify", {
        "challenge": response.data["challenge"], "code": totp(secret, int(timezone.now().timestamp() // 30)),
    }, format="json")


def test_password_staff_login_needs_mfa_and_issues_fixed_tenant_grant(space, settings, monkeypatch):
    person = make_staff(space, username="grant-staff", password=PASSWORD)
    _row, secret = enrolled(person)
    client = APIClient()
    first = device_login(client, person, settings, monkeypatch, authority="staff", makerspace=space.slug)
    assert first.status_code == 200 and first.data["mfa_required"], first.data
    done = verify(client, first, secret)
    assert done.status_code == 200, done.data
    grant = DeviceGrant.objects.get(user=person)
    assert grant.authority == "staff" and grant.staff_makerspace_id == space.pk
    assert done.data["user"]["session_authority"] == "native_staff"
    assert AuditLog.objects.filter(action="auth.staff_grant_issued", makerspace=space).exists()


def test_staff_authority_without_a_role_is_refused(space, settings, monkeypatch):
    person = User.objects.create_user("grant-member", password=PASSWORD)
    make_membership(person, space)
    response = device_login(APIClient(), person, settings, monkeypatch, authority="staff", makerspace=space.slug)
    assert response.status_code == 401
    assert not DeviceGrant.objects.filter(user=person).exists()


def test_member_grant_steps_up_from_any_primary_method(space, settings, monkeypatch):
    person = make_staff(space, username="grant-stepup", password=PASSWORD)
    _row, secret = enrolled(person)
    client = APIClient()
    first = device_login(client, person, settings, monkeypatch)
    assert first.status_code == 200 and first.data["mfa_required"], first.data
    member = verify(client, first, secret)
    assert member.status_code == 200, member.data
    member_grant = DeviceGrant.objects.get(user=person)
    assert member_grant.authority == "member"
    native = APIClient()
    native.credentials(HTTP_AUTHORIZATION=f"Bearer {member.data['access']}")
    step = native.post("/api/v1/auth/device/staff-grant",
                       {"makerspace": space.slug, **attestation(APIClient(), settings, monkeypatch)}, format="json")
    assert step.status_code == 200 and step.data["mfa_required"], step.data
    # Same 30-second step as the sign-in code: let the test reuse the step (replay guard).
    UserMFA.objects.filter(user=person).update(last_step=-1)
    done = verify(APIClient(), step, secret)
    assert done.status_code == 200, done.data
    staff = DeviceGrant.objects.get(user=person, authority="staff")
    assert staff.staff_makerspace_id == space.pk and staff.login_method == member_grant.login_method
    member_grant.refresh_from_db()
    assert member_grant.status == "active"


def test_step_up_refused_without_staff_role(space, settings, monkeypatch):
    person = User.objects.create_user("grant-nostaff", password=PASSWORD)
    member = device_login(APIClient(), person, settings, monkeypatch)
    native = APIClient()
    native.credentials(HTTP_AUTHORIZATION=f"Bearer {member.data['access']}")
    step = native.post("/api/v1/auth/device/staff-grant",
                       {"makerspace": space.slug, **attestation(APIClient(), settings, monkeypatch)}, format="json")
    assert step.status_code == 403 and step.data["code"] == "staff_access_required"


def _staff_session(space, settings, monkeypatch, username):
    person = make_staff(space, username=username, password=PASSWORD)
    _row, secret = enrolled(person)
    client = APIClient()
    first = device_login(client, person, settings, monkeypatch, authority="staff", makerspace=space.slug)
    return person, verify(client, first, secret).data


def test_role_revoke_revokes_that_tenants_staff_grants(space, settings, monkeypatch):
    person, _tokens = _staff_session(space, settings, monkeypatch, "grant-revoke")
    assert revoke_staff_grants(person, space.pk, reason="role_revoked") == 1
    assert DeviceGrant.objects.get(user=person).status == "revoked"
    assert AuditLog.objects.filter(action="auth.staff_grant_revoked", makerspace=space).exists()


def test_lost_role_revokes_the_grant_on_next_use(space, settings, monkeypatch):
    person, tokens = _staff_session(space, settings, monkeypatch, "grant-lost")
    MakerspaceMembership.staff_tracks.filter(user=person, makerspace=space).update(status="revoked")
    native = APIClient()
    native.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    assert native.get("/api/v1/auth/me").status_code == 401
    assert DeviceGrant.objects.get(user=person).status == "revoked"
    refreshed = APIClient().post("/api/v1/auth/device/refresh", {"refresh": tokens["refresh"]}, format="json")
    assert refreshed.status_code == 401
