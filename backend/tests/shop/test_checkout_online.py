"""L22 online checkout: quote = charge, 409 price_changed, rail on/off, guests, holds, lapses."""

from datetime import timedelta
from decimal import Decimal
from unittest import mock

import pytest
from django.utils import timezone

from apps.payments.models import Payment
from apps.shop.models import ShopOrder

from .helpers import client, line, manager, member, payment_for, product, shop_space, switch

pytestmark = pytest.mark.django_db
URL = "/api/v1/public/m/{slug}/shop/{tail}"


def _quote(space, who, lines):
    return client(who).post(URL.format(slug=space.slug, tail="quote/"), {"lines": lines}, format="json")


def _order(space, who, lines, **extra):
    return client(who).post(URL.format(slug=space.slug, tail="orders/"), {"lines": lines, **extra}, format="json")


def test_the_quote_is_the_charge_and_is_frozen_on_order_and_payment():
    space = shop_space("co-a", "shop.online", "shop.holds")
    _row, variant = product(space, manager(space), price="250.00", stock=5)
    buyer = member(space)
    quote = _quote(space, buyer, [line(variant, 2)]).json()
    assert Decimal(quote["total"]) == Decimal("500.00")
    placed = _order(space, buyer, [line(variant, 2)], quote_digest=quote["digest"])
    assert placed.status_code == 201, placed.content
    order = ShopOrder.objects.get(pk=placed.json()["order"]["id"])
    payment = payment_for(order)
    assert payment.amount == Decimal("500.00") and payment.subject_type == "shop_order" and payment.member == buyer
    assert payment.pricing_snapshot["digest"] == quote["digest"] == order.digest
    assert order.status == "awaiting_payment" and placed.json()["checkout_url"] == ""


def test_a_changed_price_answers_409_with_the_new_quote():
    space = shop_space("co-b", "shop.online")
    _row, variant = product(space, manager(space), price="100.00")
    buyer = member(space)
    digest = _quote(space, buyer, [line(variant)]).json()["digest"]
    variant.price = Decimal("120.00")
    variant.save(update_fields=["price"])
    response = _order(space, buyer, [line(variant)], quote_digest=digest)
    assert response.status_code == 409 and response.json()["code"] == "price_changed"
    assert not ShopOrder.objects.filter(makerspace=space).exists()


def test_without_the_rail_online_orders_are_paid_at_the_desk_and_held_48h():
    space = shop_space("co-c", "shop.online", "shop.holds")
    _row, variant = product(space, manager(space), stock=3)
    placed = _order(space, member(space), [line(variant)])
    order = ShopOrder.objects.get(pk=placed.json()["order"]["id"])
    assert order.status == "awaiting_payment"
    assert timedelta(hours=47) < order.expires_at - timezone.now() <= timedelta(hours=48)
    assert order.holds.get().quantity == 1


def test_with_the_rail_the_order_is_held_15_minutes_and_gets_a_checkout():
    space = shop_space("co-d", "shop.online", "shop.holds", "payments.enabled", "payments.shop")
    switch(space, modules=("payments",))
    _row, variant = product(space, manager(space), stock=3)
    with mock.patch("apps.shop.checkout.online_rail", return_value=True), \
            mock.patch("apps.shop.gates.online_rail", return_value=True), \
            mock.patch("apps.payments.services.create_checkout_url", return_value="https://pay.example/x"):
        placed = _order(space, member(space), [line(variant)])
    assert placed.status_code == 201, placed.content
    order = ShopOrder.objects.get(pk=placed.json()["order"]["id"])
    assert order.status == "held" and order.expires_at - timezone.now() <= timedelta(minutes=15)
    assert placed.json()["checkout_url"] == "https://pay.example/x"


def test_settlement_sells_the_held_stock():
    from apps.shop.settlement import settle_paid_order

    space = shop_space("co-e", "shop.online", "shop.holds")
    _row, variant = product(space, manager(space), stock=3)
    order = ShopOrder.objects.get(pk=_order(space, member(space), [line(variant, 2)]).json()["order"]["id"])
    Payment.objects.filter(pk=payment_for(order).pk).update(status="paid_online")
    settle_paid_order(order.pk)
    order.refresh_from_db()
    variant.refresh_from_db()
    assert order.status == "paid" and (variant.on_hand, variant.held) == (1, 0)


def test_guests_need_the_switch_and_a_confirmed_email_code():
    space = shop_space("co-f", "shop.online")
    _row, variant = product(space, manager(space))
    refused = _order(space, None, [line(variant)], guest_name="Gee", guest_email="g@example.test", email_code="1")
    assert refused.status_code == 400 and refused.json()["code"] == "guest_identity_required"
    switch(space, "shop.guest_checkout")
    with mock.patch("apps.hardware_requests.contact_verification.consume_code") as consume:
        placed = _order(space, None, [line(variant)], guest_name="Gee", guest_email="g@example.test",
                        email_code="123456")
    assert placed.status_code == 201, placed.content
    consume.assert_called_once()
    order = ShopOrder.objects.get(pk=placed.json()["order"]["id"])
    assert order.buyer is None and order.guest_email == "g@example.test" and payment_for(order).member is None
    token = placed.json()["status_token"]
    status = client().get(URL.format(slug=space.slug, tail=f"orders/{token}/"))
    assert status.status_code == 200 and status.json()["id"] == order.pk
    assert client().get(URL.format(slug=space.slug, tail="orders/forged/")).status_code == 404


def test_per_order_limits_and_sold_out_are_typed():
    space = shop_space("co-g", "shop.online", "shop.order_limits", "shop.holds")
    _row, variant = product(space, manager(space), stock=1, max_per_order=1)
    too_many = _order(space, member(space), [line(variant, 2)])
    assert too_many.status_code == 400 and too_many.json()["code"] == "per_order_limit"
    switch(space, "shop.order_limits", on=False)
    sold_out = _order(space, member(space, "b2"), [line(variant, 2)])
    assert sold_out.status_code == 409 and sold_out.json()["code"] == "out_of_stock"


def test_an_unpaid_order_lapses_and_releases_its_hold():
    from apps.shop.services_orders import lapse

    space = shop_space("co-h", "shop.online", "shop.holds")
    _row, variant = product(space, manager(space), stock=2)
    order = ShopOrder.objects.get(pk=_order(space, member(space), [line(variant)]).json()["order"]["id"])
    ShopOrder.objects.filter(pk=order.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
    lapse(order.pk)
    order.refresh_from_db()
    variant.refresh_from_db()
    assert order.status == "cancelled" and order.close_reason == "expired" and variant.held == 0
    assert payment_for(order).status == "canceled"


def test_the_member_sees_and_cancels_their_unpaid_order():
    space = shop_space("co-i", "shop.online", "shop.holds")
    _row, variant = product(space, manager(space), stock=2)
    buyer = member(space)
    order_id = _order(space, buyer, [line(variant)]).json()["order"]["id"]
    listing = client(buyer).get("/api/v1/member/shop/orders/")
    assert [row["id"] for row in listing.json()["results"]] == [order_id]
    assert client(member(space, "other")).get(f"/api/v1/member/shop/orders/{order_id}/").status_code == 404
    cancelled = client(buyer).post(f"/api/v1/member/shop/orders/{order_id}/cancel/")
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"


def test_pickup_at_an_event_needs_the_switch():
    space = shop_space("co-j", "shop.online")
    _row, variant = product(space, manager(space))
    refused = _order(space, member(space), [line(variant)], pickup_at="event", pickup_event_id=1)
    assert refused.status_code == 404 and refused.json()["code"] == "feature_off"
