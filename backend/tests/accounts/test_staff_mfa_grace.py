"""S-A: the 3-day staff-MFA grace (#128 C-1, #135 Q-A1-Q-A3) and the staff session limits."""

from datetime import timedelta

import pytest
from cryptography.fernet import Fernet
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts import mfa_grace
from apps.accounts.models import User
from apps.accounts.models_mfa_grace import StaffMfaGrace
from apps.accounts.tokens import SpaceWorksRefreshToken
from apps.audit.models import AuditLog
from apps.makerspaces.models import Makerspace
from apps.makerspaces.models_security import MakerspaceSecurityPolicy
from tests.accounts.account_factories import grant_staff_role, make_membership, make_staff
from tests.accounts.mfa_helpers import enrolled

pytestmark = pytest.mark.django_db
PASSWORD = "Grace period password 38!"


@pytest.fixture(autouse=True)
def keys(settings):
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode()
    settings.PLATFORM_STAFF_ORIGINS = ["http://localhost:5000"]
    settings.CORS_ALLOWED_ORIGINS = ["http://localhost:5000"]


@pytest.fixture
def space():
    return Makerspace.objects.create(name="Grace", slug="grace")


def client_for(user, mfa_method=None):
    if mfa_method:
        from apps.accounts.mfa_policy import credential, stamp
        stamp(user, credential(user), mfa_method)
    token = SpaceWorksRefreshToken.for_user(user).access_token
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {token}", HTTP_ORIGIN="http://localhost:5000")
    return api


def staff_url(space):
    return f"/api/v1/admin/makerspaces/{space.pk}"


def strict_url(space):
    return f"/api/v1/admin/makerspaces/{space.pk}/security-settings"


def test_unenrolled_staff_get_three_days_from_first_sign_in(space):
    staff = make_staff(space, username="grace-new", password=PASSWORD)
    login = APIClient().post("/api/v1/auth/login", {"username": staff.username, "password": PASSWORD},
                             format="json", HTTP_ORIGIN="http://localhost:5000")
    assert login.status_code == 200, login.data  # no forced enrolment: member features never block
    grace = StaffMfaGrace.objects.get(user=staff)
    assert grace.source == "upgrade" and grace.ends_at - grace.started_at == timedelta(days=3)
    assert login.data["user"]["mfa_enrolment_due"] is True
    assert login.data["user"]["mfa_grace_ends_at"] is not None
    assert AuditLog.objects.filter(action="auth.staff_mfa_grace_started", actor=staff).count() == 1
    api = client_for(staff)
    assert api.get(staff_url(space)).status_code == 200


def test_grace_end_blocks_staff_routes_only(space):
    staff = make_staff(space, username="grace-over", password=PASSWORD)
    make_membership(staff, space)
    mfa_grace.open_grace(staff, "grant")
    StaffMfaGrace.objects.filter(user=staff).update(started_at=timezone.now() - timedelta(days=4),
                                                    ends_at=timezone.now() - timedelta(days=1))
    api = client_for(staff)
    refused = api.get(staff_url(space))
    assert refused.status_code == 403 and refused.data["code"] == "mfa_enrollment_required"
    me = api.get("/api/v1/auth/me")
    assert me.status_code == 200 and me.data["mfa_enrolment_due"] is True


def test_one_grace_ever(space):
    staff = make_staff(space, username="grace-once", password=PASSWORD)
    first = mfa_grace.open_grace(staff, "grant")
    assert mfa_grace.open_grace(staff, "invite").pk == first.pk
    assert StaffMfaGrace.objects.filter(user=staff).count() == 1


def test_strict_routes_need_two_step_even_in_grace(space):
    staff = make_staff(space, username="grace-strict", password=PASSWORD)
    api = client_for(staff)
    assert api.get(staff_url(space)).status_code == 200
    refused = api.get(strict_url(space))
    assert refused.status_code == 403 and refused.data["code"] == "mfa_enrollment_required"
    enrolled(staff)
    assert client_for(staff, "totp").get(strict_url(space)).status_code == 200


def test_enrolling_closes_the_grace_and_payload_clears(space):
    staff = make_staff(space, username="grace-close", password=PASSWORD)
    mfa_grace.open_grace(staff, "grant")
    row, _ = enrolled(staff)
    mfa_grace.close_grace(staff)
    assert StaffMfaGrace.objects.get(user=staff).ends_at <= timezone.now()
    assert mfa_grace.grace_ends_at(staff) is None


def test_role_grant_signal_opens_the_grace(space, django_capture_on_commit_callbacks):
    person = User.objects.create_user("grace-granted", password=PASSWORD)
    with django_capture_on_commit_callbacks(execute=True):
        grant_staff_role(person, space, role_slug="inventory_manager")
    assert StaffMfaGrace.objects.get(user=person).source == "grant"


def test_members_get_no_grace(space):
    member = User.objects.create_user("grace-member", password=PASSWORD)
    make_membership(member, space)
    assert mfa_grace.grace_ends_at(member) is None
    assert not StaffMfaGrace.objects.filter(user=member).exists()


def _policy(space, **values):
    row, _ = MakerspaceSecurityPolicy.objects.get_or_create(makerspace=space)
    MakerspaceSecurityPolicy.objects.filter(pk=row.pk).update(values=values)


def test_staff_session_max_hours_ends_staff_routes_not_member_ones(space):
    staff = make_staff(space, username="session-max", password=PASSWORD)
    enrolled(staff)
    _policy(space, **{"security.staff_session_max_hours": 1})
    from apps.accounts.mfa_policy import credential, stamp
    stamp(staff, credential(staff), "totp")
    refresh = SpaceWorksRefreshToken.for_user(staff)
    assert refresh["staff_until"] - refresh["auth_time"] == 3600
    access = refresh.access_token
    access["staff_until"] = refresh["auth_time"] - 1  # as if the hour had passed
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {access}", HTTP_ORIGIN="http://localhost:5000")
    refused = api.get(staff_url(space))
    assert refused.status_code == 403 and refused.data["code"] == "staff_session_expired"
    assert api.get("/api/v1/auth/me").status_code == 200


def test_idle_timeout_expires_staff_time_at_refresh(space):
    from apps.accounts.staff_session_policy import stamp_rotated
    staff = make_staff(space, username="session-idle", password=PASSWORD)
    _policy(space, **{"security.staff_idle_timeout_minutes": 10})
    refresh = SpaceWorksRefreshToken.for_user(staff)
    before = refresh["staff_until"]
    stamp_rotated(staff, refresh, previous_iat=refresh["iat"] - 11 * 60)
    assert refresh["staff_until"] < before and refresh["staff_until"] <= refresh["iat"] + 60
    stamp_rotated(staff, refresh, previous_iat=refresh["iat"])
    assert refresh["staff_until"] <= refresh["iat"] + 60  # never moves later again


def test_members_carry_no_staff_clock(space):
    member = User.objects.create_user("session-member", password=PASSWORD)
    refresh = SpaceWorksRefreshToken.for_user(member)
    assert "auth_time" in refresh.payload and "staff_until" not in refresh.payload
