"""MOD-1B: the damage/lost charge route - amount input boundaries and the pricing switch (branch-exact).

test_loan_damage_lost.py owns the happy path, the photo rule and one-charge-per-row. This file pins what an amount may
look like (a refusal never writes a Payment or an audit row) and that price lists off closes the route with a typed code.
"""

import pytest

from apps.audit.models import AuditLog
from apps.hardware_requests.models import RequesterAccountability
from apps.payments.models import Payment
from tests.fixed_roles.helpers import staff_account
from tests.hardware_requests.test_loan_damage_lost import damaged_return, url
from tests.hardware_requests.test_loan_payments import quiet_storage_and_stripe  # noqa: F401
from tests.payments.pricing.helpers import client, pricing_space, switch
from tests.return_helpers import make_product

pytestmark = pytest.mark.django_db


@pytest.fixture
def row(django_capture_on_commit_callbacks):
    space, _ = pricing_space("mod1b-dmg-input")
    staff = staff_account(space, "mod1b-dmg-input-staff", "space_manager")
    request = damaged_return(space, staff, make_product(space), callbacks=django_capture_on_commit_callbacks)
    return space, staff, request, RequesterAccountability.objects.get(request=request)


@pytest.mark.parametrize("amount", ["abc", "", None, "-0.01", "-5", "1.234", "12.505", "NaN", "Infinity", "-Infinity"])
def test_a_malformed_or_negative_or_over_precise_amount_is_a_400_on_the_amount_field(row, amount):
    space, staff, request, accountability = row
    reply = client(staff).post(url(space, request, accountability), {"amount": amount}, format="json")
    assert reply.status_code == 400 and "amount" in reply.data, reply.data
    assert not Payment.objects.filter(makerspace=space).exists()
    assert not AuditLog.objects.filter(action__in=("loan.damage_charged", "loan.accountability_not_charged")).exists()


@pytest.mark.parametrize("amount, stored", [("0.01", "0.01"), ("7", "7.00"), (7, "7.00"), ("999999.99", "999999.99")])
def test_valid_amounts_at_the_precision_boundary_are_charged_exactly(row, amount, stored):
    space, staff, request, accountability = row
    reply = client(staff).post(url(space, request, accountability), {"amount": amount}, format="json")
    assert reply.status_code == 200, reply.data
    payment = Payment.objects.get(subject_type="loan_damage", subject_id=accountability.pk)
    assert str(payment.amount) == stored and payment.status == Payment.Status.PENDING
    assert AuditLog.objects.filter(action="loan.damage_charged", meta__accountability_id=accountability.pk).count() == 1


def test_with_price_lists_off_the_route_is_pricing_disabled_and_writes_nothing(row):
    space, staff, request, accountability = row
    switch(space, "charges.pricing", on=False)
    reply = client(staff).post(url(space, request, accountability), {"amount": "5.00"}, format="json")
    assert reply.status_code == 404 and reply.data["code"] == "pricing_disabled"
    assert not Payment.objects.filter(makerspace=space).exists()


def test_a_row_of_another_request_or_space_is_a_404(row, django_capture_on_commit_callbacks):
    space, staff, request, accountability = row
    other_space, _ = pricing_space("mod1b-dmg-input-other")
    outsider = staff_account(other_space, "mod1b-dmg-input-out", "space_manager")
    assert client(outsider).post(url(space, request, accountability), {"amount": "5.00"}, format="json").status_code == 404
    assert client(staff).post(url(space, request, accountability).replace(f"/accountability/{accountability.pk}/", "/accountability/999999/"),
                              {"amount": "5.00"}, format="json").status_code == 404
    assert not Payment.objects.filter(makerspace=space).exists()
