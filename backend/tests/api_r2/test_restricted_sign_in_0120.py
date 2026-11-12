"""Decision 361: a restricted or suspended person may sign in and refresh (web and native member
grant), every factor rule unchanged; the session reaches only the decision-260 admission set
because every request re-checks `access_status`. The payload says which state the account is in.
"""
from types import SimpleNamespace

import pytest
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APIClient

from apps.accounts.models import DeviceGrant, User
from apps.accounts.restricted_admission import state_may_sign_in
from apps.accounts.services_device_tokens import issue_device_token_pair
from apps.accounts.surface_policy import _active
from tests.accounts.account_factories import device_grant, make_staff
from tests.accounts.mfa_helpers import enrolled
from tests.accounts.test_device_auth import (
    CHALLENGE, LOGIN as DEVICE_LOGIN, REFRESH as DEVICE_REFRESH, attested_login, configure_apple, mock_apple_provider,
)
from tests.payments.account_helpers import make_payer
from tests.payments.test_borrower_charge_visibility import _loan_deposit
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db
WEB_LOGIN = "/api/v1/auth/login"
WEB_REFRESH = "/api/v1/auth/refresh"
ORIGIN = "http://localhost:5000"
PASSWORD = "Restricted sign-in password 361!"


@pytest.fixture(autouse=True)
def origins(settings):
    settings.CORS_ALLOWED_ORIGINS = [ORIGIN]
    settings.PASSWORD_BREACH_CHECK_ENABLED = False


def _member(slug, state):
    space = make_space(slug)
    member = make_payer(f"{slug}-member", space)
    member.set_password(PASSWORD)
    member.save(update_fields=["password"])
    debt = _loan_deposit(space, member)
    User.objects.filter(pk=member.pk).update(access_status=state)
    member.refresh_from_db()
    return space, member, debt


def _bearer(access):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


@pytest.mark.parametrize("state,code", [("restricted", "account_restricted"), ("suspended", "account_suspended")])
def test_web_sign_in_and_refresh_reach_only_own_charges(state, code):
    space, member, debt = _member(f"r361-web-{state}", state)
    browser = APIClient()
    signed_in = browser.post(WEB_LOGIN, {"username": member.username, "password": PASSWORD}, format="json")
    assert signed_in.status_code == 200, signed_in.data
    assert signed_in.data["user"]["account_status"] == state
    session = _bearer(signed_in.data["access"])
    listed = session.get(f"/api/v1/member/makerspaces/{space.pk}/payments")
    assert listed.status_code == 200 and any(row["id"] == debt.pk for row in listed.data)
    for refused in (session.get("/api/v1/auth/me"), session.get(f"/api/v1/member/makerspaces/{space.pk}/activity")):
        assert refused.status_code == 401 and refused.data["code"] == code
    refreshed = browser.post(WEB_REFRESH, HTTP_X_REFRESH_CSRF="1", HTTP_ORIGIN=ORIGIN)
    assert refreshed.status_code == 200, refreshed.data
    assert _bearer(refreshed.data["access"]).get(f"/api/v1/member/makerspaces/{space.pk}/payments").status_code == 200


def test_native_sign_in_and_refresh_issue_a_member_grant_held_to_the_admission(settings, monkeypatch):
    space, member, debt = _member("r361-app", "restricted")
    signed_in, _payload = attested_login(APIClient(), member, settings, monkeypatch, password=PASSWORD)
    assert signed_in.status_code == 200, signed_in.data
    assert signed_in.data["user"]["account_status"] == "restricted"
    grant = DeviceGrant.objects.get(user=member)
    assert grant.authority == "member" and grant.status == DeviceGrant.Status.ACTIVE
    phone = _bearer(signed_in.data["access"])
    assert phone.get(f"/api/v1/member/makerspaces/{space.pk}/payments").status_code == 200
    refused = phone.get(f"/api/v1/member/makerspaces/{space.pk}/activity")
    assert refused.status_code == 401 and refused.data["code"] == "account_restricted"
    rotated = APIClient().post(DEVICE_REFRESH, {"refresh": signed_in.data["refresh"]}, format="json")
    assert rotated.status_code == 200, rotated.data
    assert _bearer(rotated.data["access"]).get(f"/api/v1/member/makerspaces/{space.pk}/payments").status_code == 200
    assert DeviceGrant.objects.get(pk=grant.pk).status == DeviceGrant.Status.ACTIVE


def test_native_staff_sign_in_of_a_restricted_person_is_refused(settings, monkeypatch):
    space = make_space("r361-staff")
    person = make_staff(space, username="r361-staff-person", password=PASSWORD)
    enrolled(person)
    User.objects.filter(pk=person.pk).update(access_status="suspended")
    configure_apple(settings)
    challenge = APIClient().post(CHALLENGE, {"platform": "apple", "app_id": "org.spaceworks.app",
                                             "environment": "development"}, format="json").data["challenge"]
    mock_apple_provider(monkeypatch, challenge)
    refused = APIClient().post(DEVICE_LOGIN, {
        "username": person.username, "password": PASSWORD, "platform": "apple", "app_id": "org.spaceworks.app",
        "environment": "development", "challenge": challenge, "attestation": {"assertion": "opaque"},
        "authority": "staff", "makerspace": space.slug}, format="json")
    assert refused.status_code == 401
    assert not DeviceGrant.objects.filter(user=person).exists()


def test_existing_staff_grant_of_a_restricted_person_cannot_mint_tokens():
    space = make_space("r361-staff-grant")
    person = make_staff(space, username="r361-staff-grant-person")
    grant = device_grant(person, staff_makerspace_id=space.pk)
    row, _secret = enrolled(person)
    User.objects.filter(pk=person.pk).update(access_status="restricted")
    person.refresh_from_db()
    person._mfa_verified_version, person._mfa_method = str(row.version), "totp"
    with pytest.raises(AuthenticationFailed):
        issue_device_token_pair(person, grant)


@pytest.mark.parametrize("change", [{"is_active": False}, {"deletion_requested_at": timezone.now()}])
def test_deactivated_or_departing_accounts_still_cannot_sign_in(settings, monkeypatch, change):
    _space, member, _debt = _member(f"r361-gone-{len(change)}-{next(iter(change))[:6]}", "restricted")
    User.objects.filter(pk=member.pk).update(**change)
    web = APIClient().post(WEB_LOGIN, {"username": member.username, "password": PASSWORD}, format="json")
    assert web.status_code != 200 or "access" not in web.data
    native, _payload = attested_login(APIClient(), member, settings, monkeypatch, password=PASSWORD)
    assert native.status_code == 401
    assert not DeviceGrant.objects.filter(user=member).exists()


@pytest.mark.parametrize("fields", [{"retired_at": timezone.now()}, {"merged_into_id": 1}])
def test_retired_and_merged_accounts_never_hold_a_session(fields):
    shell = SimpleNamespace(account_kind="member", is_active=True, retired_at=None, is_tenant_dump_stub=False,
                            access_status="restricted", merged_into_id=None)
    for key, value in fields.items():
        setattr(shell, key, value)
    assert state_may_sign_in(shell) is False
    with pytest.raises(AuthenticationFailed):
        _active(shell)


def test_platform_accounts_must_be_active():
    platform = SimpleNamespace(account_kind="platform", retired_at=None, merged_into_id=None, access_status="restricted")
    assert state_may_sign_in(platform) is False
    assert state_may_sign_in(SimpleNamespace(account_kind="platform", access_status="active")) is True
