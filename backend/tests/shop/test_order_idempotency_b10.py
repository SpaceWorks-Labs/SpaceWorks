"""Payments audit 0.12.0 B-10: a double submit with the same Idempotency-Key places ONE order."""

import pytest

from apps.payments.models import Payment
from apps.shop.models import ShopOrder

from .helpers import client, line, manager, member, product, shop_space

pytestmark = pytest.mark.django_db
URL = "/api/v1/public/m/{slug}/shop/orders/"


def _place(space, who, variant, key=None):
    extra = {"HTTP_IDEMPOTENCY_KEY": key} if key else {}
    return client(who).post(URL.format(slug=space.slug), {"lines": [line(variant, 1)]}, format="json", **extra)


def test_the_same_key_returns_the_first_order_and_one_charge():
    space = shop_space("idem-a", "shop.online", "shop.holds")
    _row, variant = product(space, manager(space), price="10.00", stock=5)
    buyer = member(space)
    first = _place(space, buyer, variant, key="order-key-1")
    second = _place(space, buyer, variant, key="order-key-1")
    assert first.status_code == 201 and second.status_code == 201
    assert first.json()["order"]["id"] == second.json()["order"]["id"]
    assert ShopOrder.objects.filter(makerspace=space).count() == 1
    assert Payment.objects.filter(makerspace=space, subject_type="shop_order").count() == 1


def test_without_a_key_two_submits_are_two_orders():
    space = shop_space("idem-b", "shop.online", "shop.holds")
    _row, variant = product(space, manager(space), price="10.00", stock=5)
    buyer = member(space)
    assert _place(space, buyer, variant).status_code == 201
    assert _place(space, buyer, variant).status_code == 201
    assert ShopOrder.objects.filter(makerspace=space).count() == 2


def test_another_buyers_key_is_refused_not_leaked():
    space = shop_space("idem-c", "shop.online", "shop.holds")
    _row, variant = product(space, manager(space), price="10.00", stock=5)
    assert _place(space, member(space), variant, key="shared-key").status_code == 201
    stranger = _place(space, member(space, "stranger"), variant, key="shared-key")
    assert stranger.status_code == 409 and stranger.json()["code"] == "idempotency_key_reused"
