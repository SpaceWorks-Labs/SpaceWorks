"""Mutation pins (decision 457) for the loan-request workflow's rarely-hit refusals."""
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.hardware_requests import workflow
from apps.hardware_requests.models import HardwareRequest
from apps.hardware_requests.models_loans import LoanReservationPolicy
from apps.hardware_requests.renewal_workflow import check_renewal
from apps.makerspaces.models import MakerspaceMembership
from tests.fixed_roles.helpers import staff_account
from tests.hardware_requests.loan_policy_helpers import setup_loan
from tests.hardware_requests.test_new_states import space_with, submit
from tests.return_helpers import make_member, make_product, make_user

pytestmark = pytest.mark.django_db


def _refusal_code(loan, policy, **kwargs):
    with pytest.raises(ValidationError) as caught:
        check_renewal(loan, policy, **kwargs)
    return caught.value.detail["code"], str(caught.value.detail["detail"])


def test_an_inactive_membership_blocks_renewal_with_its_own_code():
    space, member, membership, _product, loan, policy, _client = setup_loan("wmp-inactive")
    check_renewal(loan, policy)  # an active membership is fine
    MakerspaceMembership.objects.filter(pk=membership.pk).update(status="revoked")
    # Staff scope still sees the revoked row, so it is named as inactive ...
    staff = staff_account(space, "wmp-inactive-sm", "space_manager")
    code, detail = _refusal_code(loan, policy, actor=staff, staff=True)
    assert code == "membership_inactive"
    assert detail == "The borrower membership is inactive."
    # ... while the member's own scope hides it, so it reads as no membership at all.
    assert _refusal_code(loan, policy)[0] == "membership_required"


def test_the_membership_module_requires_a_membership_row_to_renew():
    space, member, membership, _product, loan, policy, _client = setup_loan("wmp-nomembership")
    membership.delete()
    code, detail = _refusal_code(loan, policy)
    assert code == "membership_required"
    assert detail == "An active borrower membership is required."


def test_the_pickup_sweep_counts_a_failing_request_as_skipped_and_keeps_going():
    space = space_with("wmp-sweep", "loans.pickup_windows")
    LoanReservationPolicy.objects.create(makerspace=space, pickup_window_hours=24)
    staff = make_member("wmp-sweep-sm", space)
    product = make_product(space, available_quantity=2, total_quantity=2)
    first = workflow.accept_request(staff, submit(space, make_user("wmp-sweep-a", access_status="active"), product))
    second = workflow.accept_request(staff, submit(space, make_user("wmp-sweep-b", access_status="active"), product))
    real = workflow.expire_request

    def flaky(row, now=None):
        if row.pk == first.pk:
            raise RuntimeError("storage hiccup")
        return real(row, now=now)

    with patch("apps.hardware_requests.request_lifecycle.expire_request", flaky):
        counts = workflow.expire_due_requests(now=timezone.now() + timedelta(hours=25))
    assert counts["expired"] == 1 and counts["skipped"] == 1
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.status == HardwareRequest.Status.ACCEPTED
    assert second.status == HardwareRequest.Status.EXPIRED
