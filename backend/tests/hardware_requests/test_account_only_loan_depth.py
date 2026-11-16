"""Journey (0.12.0): an account-only borrower (member accounts on, membership off) owns
their request, so they can withdraw it and use the waitlist without a membership row."""

import pytest

from apps.accounts.models import User
from apps.hardware_requests import workflow
from apps.hardware_requests.models import HardwareRequest
from apps.hardware_requests.models_loans import LoanWaitlistEntry
from apps.hardware_requests.request_workflow import RequesterSnapshot
from tests.return_helpers import authenticated_client, make_product, make_space, make_user

pytestmark = pytest.mark.django_db


def account_only_space(slug, *features):
    space = make_space(slug)
    modules = set(space.enabled_modules or []) | {"member_accounts", "request_workflow"}
    modules.discard("membership")
    space.enabled_modules = sorted(modules)
    space.enabled_features = sorted(set(space.enabled_features or []) | {"loans.enabled", *features})
    space.save(update_fields=["enabled_modules", "enabled_features"])
    return space


def submit(space, user, product):
    snapshot = RequesterSnapshot(username=user.username, name="", email="", phone="")
    return workflow.submit_request(space, [{"product": product, "quantity": 1}], "",
                                   requester_principal=user, contact_snapshot=snapshot, audit_actor=user)


def test_account_only_borrower_withdraws_own_request():
    space = account_only_space("acct-withdraw", "loans.withdrawals")
    product = make_product(space)
    owner = make_user("acct-withdraw-owner", access_status="active")
    stranger = make_user("acct-withdraw-stranger", access_status="active")
    request = submit(space, owner, product)
    path = f"/api/v1/member/makerspaces/{space.pk}/requests/{request.pk}/withdraw"

    assert authenticated_client(stranger).post(path, {}, format="json").status_code == 404
    response = authenticated_client(owner).post(path, {}, format="json")
    assert response.status_code == 200, response.content
    request.refresh_from_db()
    assert request.status == HardwareRequest.Status.CANCELLED


def test_restricted_account_cannot_withdraw():
    space = account_only_space("acct-withdraw-restricted", "loans.withdrawals")
    owner = make_user("acct-restricted-owner", access_status="active")
    request = submit(space, owner, make_product(space))
    owner.access_status = User.AccessStatus.RESTRICTED
    owner.save(update_fields=["access_status"])
    path = f"/api/v1/member/makerspaces/{space.pk}/requests/{request.pk}/withdraw"
    assert authenticated_client(owner).post(path, {}, format="json").status_code == 404


def test_account_only_borrower_joins_lists_and_leaves_the_waitlist():
    space = account_only_space("acct-waitlist", "loans.waitlist")
    product = make_product(space, available_quantity=0, total_quantity=1, issued_quantity=1)
    owner = make_user("acct-waitlist-owner", access_status="active")
    other = make_user("acct-waitlist-other", access_status="active")
    base = f"/api/v1/member/makerspaces/{space.pk}/waitlist"
    client = authenticated_client(owner)

    joined = client.post(base, {"product_id": product.pk}, format="json")
    assert joined.status_code == 201, joined.content
    listed = client.get(base)
    assert listed.status_code == 200 and [row["id"] for row in listed.json()] == [joined.json()["id"]]
    assert authenticated_client(other).get(base).json() == []

    leave = f"{base}/{joined.json()['id']}/leave"
    assert authenticated_client(other).post(leave, {}, format="json").status_code == 404
    assert client.post(leave, {}, format="json").status_code == 200
    assert LoanWaitlistEntry.objects.get(pk=joined.json()["id"]).status == LoanWaitlistEntry.Status.CANCELLED
