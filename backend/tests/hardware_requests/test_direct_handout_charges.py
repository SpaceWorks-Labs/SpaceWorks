"""Lane L15 (A10): direct, kiosk and self-checkout loans are charged like reviewed loans."""

import inspect

import pytest

from apps.hardware_requests import direct_loan_workflow, loan_payments, self_checkout_issue
from apps.payments.models import Payment
from tests.hardware_requests.test_loan_payments import quiet_storage_and_stripe  # noqa: F401
from tests.payments.pricing.helpers import D, pricing_space, rate
from tests.return_helpers import make_issued_request, make_member, make_product

pytestmark = pytest.mark.django_db


def test_every_issue_path_runs_the_post_issue_charge_seam():
    assert "loan_payments.on_request_issued" in inspect.getsource(direct_loan_workflow.issue_direct_loan)
    assert "loan_payments.on_request_issued" in inspect.getsource(self_checkout_issue.checkout_tool)


def test_a_handout_raises_deposit_and_rental_without_ever_blocking():
    space, _ = pricing_space("direct-charges", loan_deposit_mode="fixed", loan_deposit_amount=D("5.00"),
                             loan_deposit_blocks_issue=True)
    staff = make_member("direct-charges-staff", space)
    rate(space, "loans", rental_per_loan="3.00")
    request = make_issued_request(space, staff, [(make_product(space), 2)])
    deposit = loan_payments.on_request_issued(request.pk, staff)
    assert deposit.amount == D("5.00") and deposit.status == Payment.Status.PENDING
    rental = Payment.objects.get(subject_type="loan_rental", subject_id=request.pk)
    assert rental.amount == D("6.00")
    loan_payments.on_request_issued(request.pk, staff)  # idempotent
    assert Payment.objects.filter(subject_id=request.pk).count() == 2
