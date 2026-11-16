"""Decision 216 item 11: hold -> sale -> return -> refund coordination, each step exactly once."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.payments.models import Payment, Refund, RefundCase
from apps.shop.models import ShopCheckoutHold, ShopOrder, ShopStockMovement

from .helpers import client, line, member, payment_for, product, shop_manager, shop_space

pytestmark = pytest.mark.django_db


def _place(space, buyer, variant, qty=1):
    response = client(buyer).post(f"/api/v1/public/m/{space.slug}/shop/orders/", {"lines": [line(variant, qty)]},
                                  format="json")
    assert response.status_code == 201, response.content
    return ShopOrder.objects.get(pk=response.json()["order"]["id"])


def _paid_online(space, variant, qty=2, buyer="buyer"):
    from apps.shop.settlement import settle_paid_order

    order = _place(space, member(space, buyer), variant, qty)
    Payment.objects.filter(pk=payment_for(order).pk).update(status="paid_online", provider="stripe",
                                                            stripe_payment_intent_id=f"pi_{order.pk}")
    settle_paid_order(order.pk)
    order.refresh_from_db()
    return order


def _return(seller, order, qty, disposition="restock"):
    from apps.shop.services_returns import record_return
    return record_return(order, actor=seller, rows=[{"line_id": order.lines.get().pk, "quantity": qty,
                                                     "disposition": disposition}])


def _moves(variant, kind):
    return ShopStockMovement.objects.filter(variant=variant, kind=kind).count()


def test_settlement_converts_the_hold_once_and_collection_follows():
    from apps.shop.services_orders import collect
    from apps.shop.settlement import settle_paid_order

    space = shop_space("i11-a", "shop.online", "shop.holds")
    seller = shop_manager(space)
    _row, variant = product(space, seller, stock=3)
    order = _paid_online(space, variant, qty=2)
    settle_paid_order(order.pk)  # a replayed webhook / the sweep
    variant.refresh_from_db()
    assert order.status == "paid" and (variant.on_hand, variant.held) == (1, 0)
    assert _moves(variant, "sale") == 1
    assert ShopCheckoutHold.objects.get(order=order).release_reason == "sold"
    assert collect(order, actor=seller, code=order.pickup_code).status == "collected"


def test_expiry_releases_only_its_own_hold_exactly_once():
    from apps.shop.errors import ShopRefused
    from apps.shop.services_orders import cancel_unpaid, lapse

    space = shop_space("i11-b", "shop.online", "shop.holds")
    seller = shop_manager(space)
    _row, variant = product(space, seller, stock=5)
    first = _place(space, member(space, "one"), variant, 2)
    second = _place(space, member(space, "two"), variant, 1)
    ShopOrder.objects.filter(pk=first.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
    assert lapse(first.pk).status == "cancelled"
    lapse(first.pk)
    with pytest.raises(ShopRefused):
        cancel_unpaid(first, actor=seller)
    variant.refresh_from_db()
    assert (variant.on_hand, variant.held) == (5, 1)
    assert ShopCheckoutHold.objects.get(order=first).release_reason == "expired"
    assert ShopCheckoutHold.objects.get(order=second).released_at is None
    assert payment_for(first).status == "canceled"


def test_rail_off_return_restocks_once_and_the_offline_refund_moves_no_stock():
    from apps.payments.models import ManualSettlement
    from apps.payments.services_refund_decisions import approve_case

    space = shop_space("i11-c", "shop.returns")
    seller = shop_manager(space)
    _row, variant = product(space, seller, price="40.00", stock=3)
    sale = client(seller).post(f"/api/v1/admin/makerspaces/{space.pk}/shop/pos/sale/",
                               {"lines": [line(variant, 2)], "method": "cash"}, format="json")
    order = ShopOrder.objects.get(pk=sale.json()["id"])
    _return(seller, order, 1)
    case = RefundCase.objects.get(payment=payment_for(order))
    approved = approve_case(case, actor=seller, receipt={"method": "cash", "reference": "R-1",
                                                         "refunded_at": timezone.now().isoformat()})
    variant.refresh_from_db()
    assert approved.refund.amount == Decimal("40.00") and approved.refund.status == "succeeded"
    assert ManualSettlement.objects.filter(payment=payment_for(order)).exists()  # the sale's own receipt
    assert (approved.refund.provider, approved.refund.method, approved.refund.reference) == ("manual", "cash", "R-1")
    assert variant.on_hand == 2 and _moves(variant, "returned") == 1


def test_rail_on_refund_failure_and_replay_never_restock_or_credit_twice():
    from apps.payments.services_refund_decisions import approve_case
    from apps.payments.services_refunds import settle_refund

    space = shop_space("i11-d", "shop.online", "shop.holds", "shop.returns")
    seller = shop_manager(space)
    _row, variant = product(space, seller, price="30.00", stock=3)
    order = _paid_online(space, variant, qty=2)
    _return(seller, order, 1)
    variant.refresh_from_db()
    assert variant.on_hand == 2
    case = approve_case(RefundCase.objects.get(payment=payment_for(order)), actor=seller)
    assert case.refund.status == "pending" and case.refund.amount == Decimal("30.00")
    settle_refund(case.refund, external_refund_id="", status=Refund.Status.FAILED, actor=None)
    case.refresh_from_db()
    assert case.status == "approval_failed"
    retried = approve_case(case, actor=seller)
    for _replay in range(2):
        settle_refund(retried.refund, external_refund_id="re_1", status=Refund.Status.SUCCEEDED, actor=None)
    payment = payment_for(order)
    assert Refund.counted_total(payment) == Decimal("30.00")
    assert Refund.objects.filter(payment=payment, status="succeeded").count() == 1
    variant.refresh_from_db()
    assert variant.on_hand == 2 and _moves(variant, "returned") == 1


def test_cancelling_an_uncollected_order_skips_units_already_returned():
    from apps.payments.services_refund_decisions import decline_case
    from apps.shop.services_orders import cancel_uncollected

    space = shop_space("i11-e", "shop.online", "shop.holds", "shop.returns")
    seller = shop_manager(space)
    _row, variant = product(space, seller, price="50.00", stock=5)
    order = _paid_online(space, variant, qty=3)
    _return(seller, order, 1)
    _return(seller, order, 1, disposition="write_off")
    decline_case(RefundCase.objects.get(payment=payment_for(order)), actor=seller, note="damaged on return")
    ShopOrder.objects.filter(pk=order.pk).update(paid_at=timezone.now() - timedelta(days=31))
    assert cancel_uncollected(order, actor=seller).status == "cancelled"
    variant.refresh_from_db()
    assert variant.on_hand == 4  # one restocked by the return, one by the cancel
    assert ShopStockMovement.objects.filter(variant=variant, kind="returned").count() == 2
    case = RefundCase.objects.get(payment=payment_for(order), status="open")
    assert case.due_amount == Decimal("50.00")  # only the unit never returned
