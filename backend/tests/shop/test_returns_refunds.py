"""L22 returns and refunds: a staff-approved case only; restock vs write-off; window; cancellations."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.payments.models import RefundCase, Refund
from apps.shop.models import ShopOrder, ShopOrderReturn, ShopStockMovement

from .helpers import client, line, manager, member, payment_for, product, shop_manager, shop_space, switch

pytestmark = pytest.mark.django_db


def _desk_sale(space, seller, variant, qty=2):
    response = client(seller).post(f"/api/v1/admin/makerspaces/{space.pk}/shop/pos/sale/",
                                   {"lines": [line(variant, qty)], "method": "cash"}, format="json")
    assert response.status_code == 201, response.content
    return ShopOrder.objects.get(pk=response.json()["id"])


def _return(seller, order, rows):
    return client(seller).post(f"/api/v1/admin/shop/orders/{order.pk}/returns/", {"rows": rows}, format="json")


def test_a_return_opens_a_case_and_moves_no_money():
    space = shop_space("ret-a", "shop.returns")
    seller = shop_manager(space)
    _row, variant = product(space, seller, price="100.00", stock=3)
    order = _desk_sale(space, seller, variant)
    line_id = order.lines.get().pk
    response = _return(seller, order, [{"line_id": line_id, "quantity": 1, "disposition": "restock"}])
    assert response.status_code == 200, response.content
    case = RefundCase.objects.get(payment=payment_for(order))
    assert case.area == "shop" and case.status == "open" and case.due_amount == Decimal("100.00")
    assert not Refund.objects.filter(payment=payment_for(order)).exists()
    variant.refresh_from_db()
    assert variant.on_hand == 2
    assert ShopStockMovement.objects.filter(variant=variant, kind="returned").exists()


def test_write_off_keeps_the_count_and_records_it():
    space = shop_space("ret-b", "shop.returns")
    seller = shop_manager(space)
    _row, variant = product(space, seller, stock=3)
    order = _desk_sale(space, seller, variant)
    _return(seller, order, [{"line_id": order.lines.get().pk, "quantity": 2, "disposition": "write_off"}])
    variant.refresh_from_db()
    assert variant.on_hand == 1
    assert ShopStockMovement.objects.get(variant=variant, kind="written_off").quantity == 0
    order.refresh_from_db()
    assert order.status == "refunded"


def test_cannot_return_more_than_was_sold_or_after_the_window():
    space = shop_space("ret-c", "shop.returns")
    seller = shop_manager(space)
    _row, variant = product(space, seller, stock=3)
    order = _desk_sale(space, seller, variant, qty=1)
    too_many = _return(seller, order, [{"line_id": order.lines.get().pk, "quantity": 2, "disposition": "restock"}])
    assert too_many.status_code == 400 and too_many.json()["code"] == "return_exceeds_sold"
    ShopOrder.objects.filter(pk=order.pk).update(paid_at=timezone.now() - timedelta(days=30))
    late = _return(seller, order, [{"line_id": order.lines.get().pk, "quantity": 1, "disposition": "restock"}])
    assert late.status_code == 409 and late.json()["code"] == "return_window_closed"


def test_returns_need_the_switch():
    space = shop_space("ret-d")
    seller = shop_manager(space)
    _row, variant = product(space, seller, stock=3)
    order = _desk_sale(space, seller, variant)
    response = _return(seller, order, [{"line_id": order.lines.get().pk, "quantity": 1, "disposition": "restock"}])
    assert response.status_code == 404 and response.json()["code"] == "feature_off"


def test_the_shop_manager_approves_a_cash_refund_of_a_shop_sale():
    from apps.payments.services_refund_decisions import approve_case

    space = shop_space("ret-e", "shop.returns")
    seller = shop_manager(space)
    _row, variant = product(space, seller, price="80.00", stock=3)
    order = _desk_sale(space, seller, variant, qty=1)
    _return(seller, order, [{"line_id": order.lines.get().pk, "quantity": 1, "disposition": "restock"}])
    case = RefundCase.objects.get(payment=payment_for(order))
    approved = approve_case(case, actor=seller, receipt={"method": "cash", "reference": "", "refunded_at":
                                                          timezone.now().isoformat()})
    assert approved.status == "approved" and approved.refund.amount == Decimal("80.00")


def test_direct_refund_routes_refuse_shop_sales():
    space = shop_space("ret-f")
    sm = manager(space)
    _row, variant = product(space, sm, stock=2)
    order = _desk_sale(space, sm, variant, qty=1)
    payment = payment_for(order)
    response = client(sm).post(f"/api/v1/admin/makerspaces/{space.pk}/payments/{payment.pk}/offline-refund",
                               {"amount": "1.00", "reason": "x", "receipt": {"method": "cash", "reference": "",
                                                                            "received_at": timezone.now().isoformat()}},
                               format="json")
    assert response.status_code in (400, 404, 409)
    assert not Refund.objects.filter(payment=payment).exists()


def test_an_uncollected_paid_order_is_cancelled_after_the_window_with_a_case():
    from apps.payments.models import Payment
    from apps.shop.settlement import settle_paid_order

    space = shop_space("ret-g", "shop.online", "shop.holds")
    seller = shop_manager(space)
    _row, variant = product(space, seller, price="50.00", stock=2)
    order_id = client(member(space)).post(f"/api/v1/public/m/{space.slug}/shop/orders/", {"lines": [line(variant)]},
                                          format="json").json()["order"]["id"]
    order = ShopOrder.objects.get(pk=order_id)
    Payment.objects.filter(pk=payment_for(order).pk).update(status="paid_online")
    settle_paid_order(order.pk)
    early = client(seller).post(f"/api/v1/admin/shop/orders/{order_id}/cancel/", {}, format="json")
    assert early.status_code == 409
    ShopOrder.objects.filter(pk=order_id).update(paid_at=timezone.now() - timedelta(days=31))
    late = client(seller).post(f"/api/v1/admin/shop/orders/{order_id}/cancel/", {}, format="json")
    assert late.status_code == 200 and late.json()["status"] == "cancelled"
    assert RefundCase.objects.get(payment=payment_for(order)).reason_code == "shop_uncollected"
    variant.refresh_from_db()
    assert variant.on_hand == 2


def test_cancelling_an_unpaid_order_moves_no_money():
    space = shop_space("ret-h", "shop.online", "shop.holds")
    seller = shop_manager(space)
    _row, variant = product(space, seller, stock=2)
    order_id = client(member(space)).post(f"/api/v1/public/m/{space.slug}/shop/orders/", {"lines": [line(variant)]},
                                          format="json").json()["order"]["id"]
    response = client(seller).post(f"/api/v1/admin/shop/orders/{order_id}/cancel/", {}, format="json")
    assert response.json()["status"] == "cancelled"
    order = ShopOrder.objects.get(pk=order_id)
    assert payment_for(order).status == "canceled" and not RefundCase.objects.exists()
    assert not ShopOrderReturn.objects.exists()
    switch(space)
