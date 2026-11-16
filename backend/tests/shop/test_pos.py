"""L22 front desk: sale + settlement in one transaction, receipts, cash-up and its two-person check."""

from decimal import Decimal

import pytest

from apps.payments.models import ManualSettlement, PaymentDocument
from apps.shop.models import ShopCashSession, ShopOrder

from .helpers import client, line, manager, member, payment_for, product, shop_manager, shop_space, switch

pytestmark = pytest.mark.django_db


def _sale(space, who, lines, **extra):
    return client(who).post(f"/api/v1/admin/makerspaces/{space.pk}/shop/pos/sale/",
                            {"lines": lines, "method": "cash", **extra}, format="json")


@pytest.mark.parametrize("method", ["cash", "upi", "card_machine"])
def test_a_desk_sale_records_its_settlement_and_receipt_in_one_go(method):
    space = shop_space(f"pos-{method[:3]}", "shop.receipts")
    seller = shop_manager(space)
    _row, variant = product(space, seller, price="300.00", stock=4)
    response = _sale(space, seller, [line(variant, 2)], method=method, reference="R-1")
    assert response.status_code == 201, response.content
    order = ShopOrder.objects.get(pk=response.json()["id"])
    payment = payment_for(order)
    assert order.status == "collected" and order.channel == "pos" and order.collected_by == seller
    assert payment.status == "paid_offline" and payment.amount == Decimal("600.00")
    settlement = ManualSettlement.objects.get(payment=payment)
    assert settlement.method == method and settlement.reference == "R-1"
    assert PaymentDocument.objects.filter(payment=payment, kind="receipt").exists()
    variant.refresh_from_db()
    assert variant.on_hand == 2
    receipt = client(seller).get(f"/api/v1/admin/shop/orders/{order.pk}/receipt/")
    assert receipt.status_code == 200 and receipt.json()["paid"] and receipt.json()["document_number"]


def test_a_desk_sale_never_waits_for_the_maker_checker():
    space = shop_space("pos-mc", "billing.maker_checker")
    seller = shop_manager(space)
    _row, variant = product(space, seller)
    order = ShopOrder.objects.get(pk=_sale(space, seller, [line(variant)]).json()["id"])
    assert payment_for(order).status == "paid_offline"


def test_out_of_stock_at_the_desk_writes_nothing():
    space = shop_space("pos-oos")
    seller = shop_manager(space)
    _row, variant = product(space, seller, stock=1)
    response = _sale(space, seller, [line(variant, 2)])
    assert response.status_code == 409 and response.json()["code"] == "out_of_stock"
    assert not ShopOrder.objects.filter(makerspace=space).exists()


def test_member_prices_at_the_desk_apply_the_best_discount():
    from apps.payments.models_pricing_rules import PriceDiscount

    space = shop_space("pos-mem", "shop.member_prices", "charges.discounts", "charges.pricing")
    seller = shop_manager(space)
    _row, variant = product(space, seller, price="100.00")
    buyer = member(space)
    PriceDiscount.objects.create(makerspace=space, name="Members", audience="all_members", percent_bps=1000,
                                 domains=["shop"], is_active=True, created_by=seller)
    quote = client(seller).post(f"/api/v1/admin/makerspaces/{space.pk}/shop/pos/quote/",
                                {"lines": [line(variant)], "member_id": buyer.pk}, format="json")
    assert quote.status_code == 200 and Decimal(quote.json()["total"]) == Decimal("90.00")


def test_cash_needs_an_open_session_with_cash_up_on_and_the_variance_is_counted():
    space = shop_space("pos-cash", "shop.cash_up")
    seller = shop_manager(space)
    _row, variant = product(space, seller, price="250.00")
    closed = _sale(space, seller, [line(variant)])
    assert closed.status_code == 409 and closed.json()["code"] == "cash_session_closed"
    opened = client(seller).post(f"/api/v1/admin/makerspaces/{space.pk}/shop/cash-sessions/",
                                 {"opening_float": "1000.00"}, format="json")
    assert opened.status_code == 201
    assert _sale(space, seller, [line(variant)]).status_code == 201
    session_id = opened.json()["id"]
    closing = client(seller).post(f"/api/v1/admin/shop/cash-sessions/{session_id}/close/",
                                  {"counted_cash": "1240.00"}, format="json")
    body = closing.json()
    assert body["status"] == "closed"
    assert (Decimal(body["expected_cash"]), Decimal(body["variance"])) == (Decimal("1250.00"), Decimal("-10.00"))


def test_the_two_person_check_applies_to_the_cash_up():
    space = shop_space("pos-two", "shop.cash_up", "billing.maker_checker")
    seller, other = shop_manager(space), shop_manager(space, slug="pos-two-b")
    session = client(seller).post(f"/api/v1/admin/makerspaces/{space.pk}/shop/cash-sessions/",
                                  {"opening_float": "0"}, format="json").json()
    url = f"/api/v1/admin/shop/cash-sessions/{session['id']}/"
    assert client(seller).post(url + "close/", {"counted_cash": "0"}, format="json").json()["status"] == "closing"
    assert client(seller).post(url + "confirm/").status_code == 409
    confirmed = client(other).post(url + "confirm/")
    assert confirmed.status_code == 200 and confirmed.json()["status"] == "closed"
    with pytest.raises(Exception):
        row = ShopCashSession.objects.get(pk=session["id"])
        row.note = "edited"
        row.save()


def test_paying_an_online_order_at_the_desk_sells_and_hands_it_over():
    space = shop_space("pos-desk", "shop.online", "shop.holds")
    seller = shop_manager(space)
    _row, variant = product(space, seller, stock=2)
    placed = client(member(space)).post(f"/api/v1/public/m/{space.slug}/shop/orders/", {"lines": [line(variant)]},
                                        format="json")
    order_id = placed.json()["order"]["id"]
    paid = client(seller).post(f"/api/v1/admin/shop/orders/{order_id}/take-payment/",
                               {"method": "upi", "reference": "UPI-9"}, format="json")
    assert paid.status_code == 200 and paid.json()["status"] == "collected"
    variant.refresh_from_db()
    assert (variant.on_hand, variant.held) == (1, 0)


def test_collect_by_pickup_code_and_mark_ready():
    from apps.payments.models import Payment
    from apps.shop.settlement import settle_paid_order

    space = shop_space("pos-pick", "shop.online", "shop.holds")
    switch(space, "shop.receipts")
    seller = shop_manager(space)
    _row, variant = product(space, seller, stock=2)
    order_id = client(member(space)).post(f"/api/v1/public/m/{space.slug}/shop/orders/",
                                          {"lines": [line(variant)]}, format="json").json()["order"]["id"]
    order = ShopOrder.objects.get(pk=order_id)
    Payment.objects.filter(pk=payment_for(order).pk).update(status="paid_online")
    settle_paid_order(order.pk)
    assert client(seller).post(f"/api/v1/admin/shop/orders/{order_id}/ready/").json()["status"] == "ready"
    wrong = client(seller).post(f"/api/v1/admin/shop/orders/{order_id}/collect/", {"pickup_code": "ZZZZZZ"},
                                format="json")
    assert wrong.status_code == 404 and wrong.json()["code"] == "pickup_code_invalid"
    done = client(seller).post(f"/api/v1/admin/shop/orders/{order_id}/collect/", {"pickup_code": order.pickup_code},
                               format="json")
    assert done.status_code == 200 and done.json()["status"] == "collected"
