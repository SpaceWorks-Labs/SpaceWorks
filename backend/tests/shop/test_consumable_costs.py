"""Decision 216 item 11: a shop sale of a linked inventory consumable records its cost once.

`shop_sale` keys on the sale `ShopStockMovement` and freezes the item's price at sale time;
a restock (`shop_return`) reverses the returned units at THAT price, a write-off keeps it.
Shop module or `inventory.consumables` off -> no record and the sale is unaffected.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.inventory.models import InventoryProduct
from apps.machines.models_tracking import ConsumableCostRecord
from apps.shop.consumable_costs import record_sale_costs, reverse_return_costs
from apps.shop.models import ShopOrder, ShopStockMovement
from apps.shop.services_catalogue import save_product

from .helpers import client, line, member, module_off, payment_for, shop_manager, shop_space, switch

pytestmark = pytest.mark.django_db
FEATURES = ("shop.consumable_link", "shop.returns", "inventory.consumables")


def _linked(space, seller, *, unit_cost="2.50", stock=10):
    item = InventoryProduct.objects.create(makerspace=space, name="Resin", is_consumable=True,
                                           available_quantity=stock, total_quantity=stock,
                                           unit_cost=Decimal(unit_cost), cost_currency="INR", cost_unit="count")
    row = save_product(space, {"name": "Resin bottle", "variants": [
        {"name": "1 L", "price": 30, "linked_product_id": item.pk}]}, actor=seller)
    return item, row.variants.get()


def _desk_sale(space, seller, variant, qty=3):
    response = client(seller).post(f"/api/v1/admin/makerspaces/{space.pk}/shop/pos/sale/",
                                   {"lines": [line(variant, qty)], "method": "cash"}, format="json")
    assert response.status_code == 201, response.content
    return ShopOrder.objects.get(pk=response.json()["id"])


def _return(seller, order, quantity, disposition="restock"):
    response = client(seller).post(f"/api/v1/admin/shop/orders/{order.pk}/returns/", {"rows": [
        {"line_id": order.lines.get().pk, "quantity": quantity, "disposition": disposition}]}, format="json")
    assert response.status_code == 200, response.content


def _costs(space, kind=None):
    rows = ConsumableCostRecord.objects.filter(makerspace=space)
    return list(rows.filter(source_kind=kind) if kind else rows)


def test_a_linked_sale_records_one_cost_at_the_sale_price():
    space = shop_space("ccost-a", *FEATURES)
    seller = shop_manager(space)
    item, variant = _linked(space, seller)
    order = _desk_sale(space, seller, variant, qty=3)
    [cost] = _costs(space)
    sale = ShopStockMovement.objects.get(order=order, kind="sale")
    assert (cost.source_kind, cost.source_id) == ("shop_sale", sale.pk)
    assert cost.quantity == 3 and cost.measurement_unit == "count" and cost.currency == "INR"
    assert cost.cost_total_minor == 750
    # A later price change never reprices it, and a second pass records nothing new.
    InventoryProduct.objects.filter(pk=item.pk).update(unit_cost=Decimal("9.00"))
    assert record_sale_costs(order, actor=seller) == [cost]
    assert len(_costs(space)) == 1 and _costs(space)[0].cost_total_minor == 750


def test_a_replayed_online_settlement_records_the_cost_once():
    from apps.payments.models import Payment
    from apps.shop.settlement import settle_paid_order

    space = shop_space("ccost-b", *FEATURES, "shop.online", "shop.holds")
    seller = shop_manager(space)
    _item, variant = _linked(space, seller)
    order_id = client(member(space)).post(f"/api/v1/public/m/{space.slug}/shop/orders/",
                                          {"lines": [line(variant, 2)]}, format="json").json()["order"]["id"]
    order = ShopOrder.objects.get(pk=order_id)
    Payment.objects.filter(pk=payment_for(order).pk).update(status="paid_online")
    settle_paid_order(order.pk)
    settle_paid_order(order.pk)
    order.refresh_from_db()
    assert order.status == "paid"
    record_sale_costs(order, actor=None)
    [cost] = _costs(space)
    assert cost.source_kind == "shop_sale" and cost.quantity == 2 and cost.cost_total_minor == 500


def test_a_restock_reverses_once_at_the_sale_price_and_nets_to_zero():
    space = shop_space("ccost-c", *FEATURES)
    seller = shop_manager(space)
    item, variant = _linked(space, seller, unit_cost="0.333")
    order = _desk_sale(space, seller, variant, qty=3)
    [sale] = _costs(space, "shop_sale")
    InventoryProduct.objects.filter(pk=item.pk).update(unit_cost=Decimal("5.00"))  # ignored by reversals
    _return(seller, order, 1)
    [first] = _costs(space, "shop_return")
    assert first.quantity == 1 and first.unit_price_minor_per_measurement_unit == sale.unit_price_minor_per_measurement_unit
    assert reverse_return_costs(order, actor=seller) == []  # replay: nothing new
    _return(seller, order, 2)
    reversals = _costs(space, "shop_return")
    assert len(reversals) == 2 and sum(r.quantity for r in reversals) == sale.quantity
    assert sum(r.cost_total_minor for r in reversals) == sale.cost_total_minor  # exact net, no rounding drift
    movements = set(ShopStockMovement.objects.filter(order=order, kind="returned").values_list("pk", flat=True))
    assert {r.source_id for r in reversals} == movements


def test_a_write_off_keeps_the_cost():
    space = shop_space("ccost-d", *FEATURES)
    seller = shop_manager(space)
    _item, variant = _linked(space, seller)
    order = _desk_sale(space, seller, variant, qty=2)
    _return(seller, order, 2, disposition="write_off")
    assert len(_costs(space, "shop_sale")) == 1 and not _costs(space, "shop_return")


def test_an_uncollected_cancellation_reverses_only_the_units_still_out():
    from apps.payments.models import Payment
    from apps.shop.settlement import settle_paid_order

    space = shop_space("ccost-e", *FEATURES, "shop.online", "shop.holds")
    seller = shop_manager(space)
    _item, variant = _linked(space, seller)
    order_id = client(member(space)).post(f"/api/v1/public/m/{space.slug}/shop/orders/",
                                          {"lines": [line(variant, 3)]}, format="json").json()["order"]["id"]
    order = ShopOrder.objects.get(pk=order_id)
    Payment.objects.filter(pk=payment_for(order).pk).update(status="paid_online")
    settle_paid_order(order.pk)
    _return(seller, ShopOrder.objects.get(pk=order_id), 1, disposition="write_off")
    ShopOrder.objects.filter(pk=order_id).update(paid_at=timezone.now() - timedelta(days=31))
    switch(space, "shop.returns", on=False)  # cancellation does not need the returns switch
    response = client(seller).post(f"/api/v1/admin/shop/orders/{order_id}/cancel/", {}, format="json")
    assert response.status_code == 200, response.content
    [reversal] = _costs(space, "shop_return")
    [sale] = _costs(space, "shop_sale")
    assert reversal.quantity == 2 and reversal.cost_total_minor == sale.cost_total_minor - 250


def test_consumables_capability_off_records_nothing_and_the_sale_stands():
    space = shop_space("ccost-f", "shop.consumable_link", "shop.returns")
    seller = shop_manager(space)
    item, variant = _linked(space, seller)
    order = _desk_sale(space, seller, variant, qty=2)
    item.refresh_from_db()
    assert order.status == "collected" and item.available_quantity == 8
    assert not _costs(space)
    _return(seller, order, 1)  # nothing recorded -> nothing to reverse
    assert not _costs(space)


def test_shop_module_off_records_nothing():
    space = shop_space("ccost-g", *FEATURES)
    seller = shop_manager(space)
    item, variant = _linked(space, seller)
    from apps.shop.orders_core import create_order
    from apps.shop.pricing import priced_basket
    from apps.shop.settlement import settle_locked

    order = create_order(space, priced_basket(space, [line(variant, 2)], public=False), channel="online",
                         status="held", actor=seller)
    module_off(space)
    # Money that settles after the shop went off still sells the stock; no cost is recorded.
    order = ShopOrder.objects.select_related("makerspace").get(pk=order.pk)
    settle_locked(order, actor=None)
    item.refresh_from_db()
    assert ShopOrder.objects.get(pk=order.pk).status == "paid" and item.available_quantity == 8
    assert not _costs(space)


def test_own_stock_sales_record_nothing():
    from .helpers import product

    space = shop_space("ccost-h", *FEATURES)
    seller = shop_manager(space)
    _row, variant = product(space, seller, stock=3)
    _desk_sale(space, seller, variant, qty=2)
    assert not _costs(space)


def test_costs_stay_in_their_own_space():
    space = shop_space("ccost-i", *FEATURES)
    other = shop_space("ccost-j", *FEATURES)
    seller = shop_manager(space)
    _item, variant = _linked(space, seller)
    _desk_sale(space, seller, variant, qty=1)
    assert len(_costs(space)) == 1 and not _costs(other)
    # A link pointing at another space's item is never priced from it.
    foreign = InventoryProduct.objects.create(makerspace=other, name="Theirs", is_consumable=True,
                                              available_quantity=5, total_quantity=5, unit_cost=Decimal("1.00"),
                                              cost_currency="INR", cost_unit="count")
    from apps.shop.models import ShopVariant
    from apps.shop.orders_core import create_order
    from apps.shop.pricing import priced_basket
    from apps.inventory.availability import sell_shop_stock

    order = create_order(space, priced_basket(space, [line(variant, 1)], public=False), channel="online",
                         status="held", actor=seller)
    ShopVariant.objects.filter(pk=variant.pk).update(linked_product=foreign)
    variant.refresh_from_db()
    sell_shop_stock(order, [(variant, 1)], actor=seller)
    order = ShopOrder.objects.select_related("makerspace").get(pk=order.pk)
    assert record_sale_costs(order, actor=seller) == []
    assert len(_costs(space)) == 1 and not _costs(other)


def test_the_usage_report_labels_and_nets_shop_costs():
    from apps.operations.reports_ab_consumables import build_consumable_usage

    space = shop_space("ccost-k", *FEATURES)
    switch(space, modules=("machines", "reports"))
    seller = shop_manager(space)
    _item, variant = _linked(space, seller)
    order = _desk_sale(space, seller, variant, qty=2)
    _return(seller, order, 1)
    rows = {row["source"]: row for row in build_consumable_usage(space.pk, actor=None).records}
    assert rows["shop_sale"]["consumed_quantity"] == 2 and rows["shop_sale"]["cost_total_minor"] == 500
    assert rows["shop_return"]["consumed_quantity"] == -1 and rows["shop_return"]["cost_total_minor"] == -250
    assert rows["shop_sale"]["material"] == "Resin" and rows["shop_sale"]["currency"] == "INR"
