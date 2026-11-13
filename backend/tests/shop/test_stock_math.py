"""L22 stock math (inventory/availability_shop.py): never below zero, holds, bundles, links."""

import threading
from datetime import timedelta

import pytest
from django.db import close_old_connections
from django.utils import timezone

from apps.inventory.availability import (
    OutOfStock, adjust_shop_stock, hold_shop_checkout, release_shop_hold, sell_shop_stock, shop_sellable,
    shop_stock_units,
)
from apps.shop.models import ShopCheckoutHold, ShopOrder, ShopStockMovement

from .helpers import line, manager, member, product, shop_space, switch

pytestmark = pytest.mark.django_db


def _order(space, actor):
    from apps.shop.orders_core import create_order
    from apps.shop.pricing import priced_basket
    return lambda variant, qty=1: create_order(space, priced_basket(space, [line(variant, qty)], public=False),
                                               channel="online", status="held", actor=actor)


def test_holds_count_against_stock_and_release_on_expiry():
    space = shop_space("stk-a", "shop.online", "shop.holds")
    sm = manager(space)
    _row, variant = product(space, sm, stock=2)
    order = _order(space, sm)(variant, 2)
    hold_shop_checkout(order, [(variant, 2)], expires_at=timezone.now() + timedelta(minutes=15))
    variant.refresh_from_db()
    assert variant.held == 2 and shop_sellable(variant) == 0
    other = _order(space, sm)(variant, 1)
    with pytest.raises(OutOfStock):
        hold_shop_checkout(other, [(variant, 1)], expires_at=timezone.now())
    release_shop_hold(order, ShopCheckoutHold.Reason.EXPIRED)
    variant.refresh_from_db()
    assert variant.held == 0 and shop_sellable(variant) == 2


def test_a_sale_spends_its_hold_and_writes_a_movement():
    space = shop_space("stk-b")
    sm = manager(space)
    _row, variant = product(space, sm, stock=3)
    order = _order(space, sm)(variant, 2)
    hold_shop_checkout(order, [(variant, 2)], expires_at=timezone.now() + timedelta(minutes=15))
    sell_shop_stock(order, [(variant, 2)], actor=sm)
    variant.refresh_from_db()
    assert (variant.on_hand, variant.held) == (1, 0)
    sale = ShopStockMovement.objects.get(variant=variant, kind="sale")
    assert (sale.quantity, sale.balance_after, sale.order_id) == (-2, 1, order.pk)
    assert ShopCheckoutHold.objects.get(order=order).release_reason == "sold"


def test_stock_never_goes_below_zero_or_below_holds():
    space = shop_space("stk-c")
    sm = manager(space)
    _row, variant = product(space, sm, stock=1)
    order = _order(space, sm)(variant, 1)
    with pytest.raises(OutOfStock):
        sell_shop_stock(order, [(variant, 2)], actor=sm)
    hold_shop_checkout(order, [(variant, 1)], expires_at=timezone.now() + timedelta(minutes=15))
    with pytest.raises(OutOfStock):
        adjust_shop_stock(variant, -1, kind="damage", actor=sm, reason="dropped")
    variant.refresh_from_db()
    assert variant.on_hand == 1


def test_movements_are_append_only():
    space = shop_space("stk-d")
    sm = manager(space)
    _row, variant = product(space, sm, stock=1)
    row = ShopStockMovement.objects.get(variant=variant)
    row.reason = "edited"
    with pytest.raises(Exception):
        row.save()


def test_bundle_kits_take_their_parts():
    from apps.shop.services_catalogue import save_product

    space = shop_space("stk-e", "shop.bundles")
    sm = manager(space)
    _p, part = product(space, sm, name="Part", stock=5)
    kit = save_product(space, {"kind": "kit", "name": "Kit", "bundle_mode": True, "price": 10,
                               "components": [{"variant_id": part.pk, "quantity": 2}]}, actor=sm)
    kit_variant = kit.variants.get()
    assert shop_sellable(kit_variant, bundles=True) == 2
    assert shop_stock_units(kit_variant, 2, bundles=True) == [(part, 4)]
    order = _order(space, sm)(kit_variant, 2)
    sell_shop_stock(order, shop_stock_units(kit_variant, 2, bundles=True), actor=sm)
    part.refresh_from_db()
    assert part.on_hand == 1


def test_a_linked_consumable_is_one_count_with_the_inventory():
    from apps.inventory.models import InventoryProduct
    from apps.shop.services_catalogue import save_product

    space = shop_space("stk-f", "shop.consumable_link")
    sm = manager(space)
    item = InventoryProduct.objects.create(makerspace=space, name="Resin", is_consumable=True,
                                           available_quantity=4, total_quantity=4)
    row = save_product(space, {"name": "Resin bottle", "variants": [{"name": "1 L", "price": 30,
                                                                     "linked_product_id": item.pk}]}, actor=sm)
    variant = row.variants.get()
    assert shop_sellable(variant) == 4
    order = _order(space, sm)(variant, 3)
    sell_shop_stock(order, [(variant, 3)], actor=sm)
    item.refresh_from_db()
    assert item.available_quantity == 1


@pytest.mark.django_db(transaction=True)
def test_two_concurrent_checkouts_for_the_last_unit_sell_it_once():
    from apps.shop.checkout import Buyer, place_online_order
    from apps.shop.errors import ShopRefused

    space = shop_space("stk-g", "shop.online", "shop.holds")
    sm = manager(space)
    _row, variant = product(space, sm, stock=1)
    buyers = [member(space, f"b{i}") for i in range(2)]
    results, barrier = [], threading.Barrier(2)

    def attempt(person):
        close_old_connections()
        barrier.wait()
        try:
            place_online_order(space, Buyer(person, person.username, person.email, person), {"lines": [line(variant)]})
            results.append("ok")
        except ShopRefused as exc:
            results.append(exc.code)
        finally:
            close_old_connections()

    threads = [threading.Thread(target=attempt, args=(person,)) for person in buyers]
    [thread.start() for thread in threads]
    [thread.join() for thread in threads]
    assert sorted(results) == ["ok", "out_of_stock"]
    variant.refresh_from_db()
    assert variant.held == 1 and variant.on_hand == 1
    assert ShopOrder.objects.filter(makerspace=space).count() == 1
