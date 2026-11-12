"""Decision 260 at the session boundary (lane MOB-AUTH2, decision 358 C).

A restricted or suspended account may still read and pay its OWN charges -- paying is how a
restriction is cleared -- and sign out, on the web and on the phone. Every other route keeps
the typed 401 `account_restricted` / `account_suspended`; a REVOKED member stays refused, and
a restricted account's staff grant exercises nothing.
"""
import pytest
from rest_framework.test import APIClient

from apps.accounts.models import DeviceGrant, User
from apps.accounts.services_device_tokens import issue_device_token_pair
from apps.accounts.tokens import SpaceWorksRefreshToken
from apps.makerspaces.models import MakerspaceMembership
from tests.accounts.account_factories import device_grant, make_staff
from tests.accounts.mfa_helpers import enrolled
from tests.payments.account_helpers import make_payer
from tests.payments.test_borrower_charge_visibility import _borrower, _loan_deposit
from tests.return_helpers import make_member, make_space

pytestmark = pytest.mark.django_db
STATES = [("restricted", "account_restricted"), ("suspended", "account_suspended")]
ME = "/api/v1/auth/me"


def _payments(space):
    return f"/api/v1/member/makerspaces/{space.pk}/payments"


def _web(user):
    token = SpaceWorksRefreshToken.for_user(user)  # minted while the account is still active
    token["surface"] = "member"
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


def _phone(user, space=None, grant=None):
    access, _refresh, _family = issue_device_token_pair(user, grant or device_grant(user))
    client = APIClient()
    headers = {"HTTP_AUTHORIZATION": f"Bearer {access}"}
    if space is not None:
        headers["HTTP_X_MAKERSPACE_ID"] = str(space.pk)
    client.credentials(**headers)
    return client


def _restrict(user, state):
    User.objects.filter(pk=user.pk).update(access_status=state)


@pytest.mark.parametrize("state,code", STATES)
def test_web_session_reads_and_pays_own_charges_and_nothing_else(state, code):
    space = make_space(f"r260-web-{state}")
    member = make_payer(f"r260-web-{state}-member", space)
    debt = _loan_deposit(space, member)  # provider=unclaimed: the pay route answers "at the desk"
    client = _web(member)
    _restrict(member, state)
    listed = client.get(_payments(space))
    assert listed.status_code == 200, listed.data
    assert any(row["id"] == debt.pk for row in listed.data)
    pay = client.post(f"{_payments(space)}/{debt.pk}/checkout")
    assert pay.status_code == 503 and pay.data["code"] == "payments_unavailable"  # reached the view
    assert client.get(f"/api/v1/member/makerspaces/{space.pk}/payment-documents").status_code == 200
    summary = client.get(f"/api/v1/member/makerspaces/{space.pk}/my-usage")  # outstanding per currency
    assert summary.status_code == 200 and summary.data["usage_available"] is False
    for refused in (client.get(ME), client.get(f"/api/v1/member/makerspaces/{space.pk}/activity")):
        assert refused.status_code == 401 and refused.data["code"] == code
    assert client.post("/api/v1/auth/logout-all").status_code == 200


@pytest.mark.parametrize("state,code", STATES)
def test_native_member_grant_reads_and_pays_own_charges_and_signs_out(state, code):
    space = make_space(f"r260-app-{state}")
    member = make_payer(f"r260-app-{state}-member", space)
    debt = _loan_deposit(space, member)
    grant = device_grant(member)
    plain, selected = _phone(member, grant=grant), _phone(member, space, grant=grant)
    _restrict(member, state)
    for client in (plain, selected):
        listed = client.get(_payments(space))
        assert listed.status_code == 200, listed.data
        assert any(row["id"] == debt.pk for row in listed.data)
    intent = selected.post(f"{_payments(space)}/{debt.pk}/mobile-intent")
    assert intent.status_code == 503 and intent.data["code"] == "payments_unavailable"
    refused = selected.get(f"/api/v1/member/makerspaces/{space.pk}/activity")
    assert refused.status_code == 401 and refused.data["code"] == code
    assert plain.get(ME).status_code == 401 and plain.get(ME).data["code"] == code
    assert plain.post("/api/v1/auth/device/logout").status_code == 200
    assert DeviceGrant.objects.get(pk=grant.pk).status == DeviceGrant.Status.REVOKED


def test_account_only_borrower_keeps_the_admission_while_restricted():
    space = make_space("r260-borrower")
    borrower = _borrower(space, "r260-borrower-user")
    _loan_deposit(space, borrower)
    client = _phone(borrower, space)
    _restrict(borrower, "restricted")
    assert client.get(_payments(space)).status_code == 200
    assert client.get(f"/api/v1/member/makerspaces/{space.pk}/activity").status_code == 401


def test_revoked_member_is_still_refused_while_restricted():
    space = make_space("r260-revoked")
    member = make_member("r260-revoked-member", space, membership_role="custom", role="requester")
    MakerspaceMembership.objects.filter(makerspace=space, user=member).update(status="revoked")
    _loan_deposit(space, member)
    web, phone = _web(member), _phone(member)
    _restrict(member, "restricted")
    assert web.get(_payments(space)).status_code == 403
    assert phone.get(_payments(space)).status_code == 403


def test_restricted_staff_grant_reaches_nothing():
    space = make_space("r260-staff")
    person = make_staff(space, username="r260-staff-person")
    grant = device_grant(person, staff_makerspace_id=space.pk)
    row, _secret = enrolled(person)
    person._mfa_verified_version, person._mfa_method = str(row.version), "totp"
    client = _phone(person, grant=grant)
    _loan_deposit(space, person)
    _restrict(person, "suspended")
    refused = client.get(_payments(space))
    assert refused.status_code == 401 and refused.data["code"] == "account_suspended"


def test_deactivated_account_is_not_admitted():
    space = make_space("r260-inactive")
    member = make_payer("r260-inactive-member", space)
    _loan_deposit(space, member)
    client = _web(member)
    User.objects.filter(pk=member.pk).update(access_status="restricted", is_active=False)
    assert client.get(_payments(space)).status_code == 401
