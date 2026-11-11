"""#184 matrix, lending: damage/lost charges (G1) and the public price preview (G2) in each mode."""

from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.hardware_requests.models import RequesterAccountability
from tests.fixed_roles.helpers import staff_account
from tests.hardware_requests.test_loan_damage_lost import damaged_return, url
from tests.hardware_requests.test_loan_payments import quiet_storage_and_stripe  # noqa: F401
from tests.money_modes.helpers import (
    FREE, MODES, ONLINE, assert_mode_outcome, charges, fake_provider, master_off, set_mode,
)
from tests.payments.pricing.helpers import client, pricing_space, rate
from tests.return_helpers import make_product

pytestmark = pytest.mark.django_db


def charges_url(space, request):
    return f"/api/v1/admin/makerspace/{space.pk}/requests/{request.pk}/charges"


@pytest.mark.parametrize("mode", MODES)
def test_damage_charge_follows_the_lending_mode(mode, monkeypatch, django_capture_on_commit_callbacks):
    space, _ = pricing_space(f"mm-dmg-{mode}")
    staff = staff_account(space, f"mm-dmg-{mode}-staff", "space_manager")
    rate(space, "loans", damage="12.00")
    product = make_product(space, unit_cost=Decimal("40"))
    request = damaged_return(space, staff, product, callbacks=django_capture_on_commit_callbacks)
    row = RequesterAccountability.objects.get(request=request)
    set_mode(space, "loans", mode)
    checkout = fake_provider(monkeypatch) if mode == ONLINE else None

    listed = client(staff).get(charges_url(space, request))
    assert listed.status_code == 200, listed.data
    assert listed.data["charges_enabled"] is (mode != FREE)
    with django_capture_on_commit_callbacks(execute=True):
        response = client(staff).post(url(space, request, row), {"amount": "15.00"}, format="json")
    if mode == FREE:
        assert response.status_code == 404 and response.data["code"] == "charges_off"
    else:
        assert response.status_code == 200, response.data
    payment = assert_mode_outcome(mode, charges(space, "loan_damage"), checkout)
    if payment is not None:
        assert payment.amount == Decimal("15.00") and payment.member_id == request.requester_id


def test_the_master_switch_alone_makes_lending_free(django_capture_on_commit_callbacks):
    space, _ = pricing_space("mm-dmg-master")
    staff = staff_account(space, "mm-dmg-master-staff", "space_manager")
    product = make_product(space, unit_cost=Decimal("40"))
    request = damaged_return(space, staff, product, damaged=0, missing=1, callbacks=django_capture_on_commit_callbacks)
    row = RequesterAccountability.objects.get(request=request)
    master_off(space)
    refused = client(staff).post(url(space, request, row), {"amount": "40.00"}, format="json")
    assert refused.status_code == 404 and refused.data["code"] == "charges_off"
    assert charges(space, "loan_lost") == []


@pytest.mark.parametrize("mode", MODES)
def test_the_public_loan_price_preview_exists_only_while_lending_is_paid(mode):
    space, _ = pricing_space(f"mm-quote-{mode}")
    rate(space, "loans", rental_per_day="4.00")
    product = make_product(space)
    set_mode(space, "loans", mode)
    response = APIClient().post(f"/api/v1/public/{space.slug}/pricing/quote",
                                {"domain": "loans", "items": [{"product_id": product.pk, "quantity": 1}], "days": 2},
                                format="json")
    if mode == FREE:
        assert response.status_code == 404 and response.data["code"] == "charges_off"
    else:
        assert response.status_code == 200, response.data
        assert Decimal(response.data["quote"]["total"]) == Decimal("8.00")
