"""Lane L15 (A6/A8): the public price preview -- anonymous vs member, hidden data, switches."""

import pytest
from rest_framework.test import APIClient

from apps.payments.models import PriceDiscount
from tests.payments.pricing.helpers import D, client, member, pricing_space, rate, switch
from tests.return_helpers import make_product

pytestmark = pytest.mark.django_db


def url(space):
    return f"/api/v1/public/{space.slug}/pricing/quote"


@pytest.fixture
def setup():
    space, manager = pricing_space("quote-api", "charges.discounts", loan_deposit_mode="fixed",
                                   loan_deposit_amount=D("10.00"), loan_late_fee_per_day=D("1.00"))
    rate(space, "loans", rental_per_day="4.00")
    PriceDiscount.objects.create(makerspace=space, name="Members", audience="all_members", percent_bps=2500,
                                 created_by=manager)
    return space, make_product(space)


def body(product, **extra):
    return {"domain": "loans", "items": [{"product_id": product.pk, "quantity": 1}], "days": 2, **extra}


def test_anonymous_sees_the_public_price_and_what_members_pay(setup):
    space, product = setup
    response = APIClient().post(url(space), body(product), format="json")
    assert response.status_code == 200, response.data
    data = response.data
    assert D(data["quote"]["total"]) == D("8.00") and D(data["members_total"]) == D("6.00")
    assert data["deposit"] == {"amount": "10.00", "refundable": True}
    assert D(data["policy"]["late_per_day"]) == D("1.00") and data["digest"]
    assert "storage_location" not in str(data) and "qr" not in str(data).lower()


def test_a_member_gets_their_own_price(setup):
    space, product = setup
    response = client(member(space)).post(url(space), body(product), format="json")
    assert D(response.data["quote"]["total"]) == D("6.00") and response.data["member_price_applied"] is True
    assert response.data["members_total"] is None


def test_hidden_items_and_switched_off_pricing_are_not_found(setup):
    space, product = setup
    hidden = make_product(space, name="Hidden", is_public=False)
    assert APIClient().post(url(space), body(hidden), format="json").status_code == 404
    switch(space, "charges.pricing", on=False)
    assert APIClient().post(url(space), body(product), format="json").status_code == 404


def test_a_member_may_not_quote_someone_elses_loan(setup):
    space, product = setup
    from tests.return_helpers import make_issued_request
    from tests.fixed_roles.helpers import staff_account
    request = make_issued_request(space, staff_account(space, "quote-sm", "space_manager"), [(product, 1)])
    response = client(member(space)).post(url(space), {"domain": "loans", "request_id": request.pk}, format="json")
    assert response.status_code == 404


def test_rooms_and_events_quote_by_public_token():
    from datetime import timedelta
    from django.utils import timezone
    from tests.payments.pricing.test_domain_seams import install
    from tests.payments.test_track3_booking_event_charging import bookable
    space, _ = pricing_space("quote-token")
    install(space, "bookings")
    room = bookable(space, amount="7.00")
    starts = timezone.now() + timedelta(days=1)
    response = APIClient().post(url(space), {"domain": "bookings", "space_token": str(room.public_token),
                                             "starts_at": starts.isoformat(),
                                             "ends_at": (starts + timedelta(hours=1)).isoformat()}, format="json")
    assert response.status_code == 200, response.data
    assert D(response.data["quote"]["total"]) == D("7.00")
    import uuid
    missing = APIClient().post(url(space), {"domain": "bookings", "space_token": str(uuid.uuid4())}, format="json")
    assert missing.status_code == 404
