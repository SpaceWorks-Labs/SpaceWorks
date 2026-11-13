"""Switch-off stops new stock commitments and preserves existing order accounting."""

import pytest

from apps.inventory.models import InventoryProduct
from apps.makerspaces.models import Makerspace
from apps.shop.checkout import Buyer, place_online_order
from apps.shop.errors import ShopRefused
from apps.shop.models import ShopOrder
from apps.shop.pricing import priced_basket
from apps.shop.public import product_payload
from apps.shop.services_catalogue import save_product
from apps.shop.services_pos import collect_payment, pos_sale
from apps.shop.services_returns import record_return
from tests.shop.helpers import line, manager, member, shop_space, switch

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("bundle", [False, True])
def test_link_off_blocks_new_direct_and_bundle_sales_but_keeps_order_accounting(bundle):
    space = shop_space("link-off-bundle" if bundle else "link-off-direct", "shop.consumable_link",
                       "shop.bundles", "shop.online", "shop.holds", "shop.returns", "shop.public_stock")
    seller = manager(space)
    item = InventoryProduct.objects.create(makerspace=space, name="Shared resin", is_consumable=True,
                                           available_quantity=8, total_quantity=8)
    linked = save_product(space, {"name": "Resin bottle", "variants": [
        {"name": "One litre", "price": 30, "linked_product_id": item.pk}]}, actor=seller)
    linked_variant = linked.variants.get()
    product = linked
    units = 1
    if bundle:
        product = save_product(space, {"kind": "kit", "name": "Resin pack", "bundle_mode": True,
                                      "price": 50, "components": [
                                          {"variant_id": linked_variant.pk, "quantity": 2}]}, actor=seller)
        units = 2
    variant = product.variants.get()
    person = member(space)
    buyer = Buyer(person, person.username, person.email, person)
    order, _payment = place_online_order(space, buyer, {"lines": [line(variant)]})
    stale_space = Makerspace.objects.get(pk=space.pk)
    switch(space, "shop.consumable_link", on=False)

    shown = product_payload(space, product)
    assert shown["variants"][0]["sold_out"] is True
    assert shown["variants"][0]["stock_count"] is None
    for public in (True, False):
        with pytest.raises(ShopRefused) as caught:
            priced_basket(space, [line(variant)], public=public)
        assert caught.value.status_code == 404 and caught.value.code == "feature_off"
    with pytest.raises(ShopRefused):
        place_online_order(stale_space, buyer, {"lines": [line(variant)]})
    with pytest.raises(ShopRefused):
        pos_sale(stale_space, actor=seller, lines=[line(variant)])
    assert ShopOrder.objects.filter(makerspace=space).count() == 1
    item.refresh_from_db()
    assert item.available_quantity == 8
    linked_variant.refresh_from_db()
    assert linked_variant.linked_product_id == item.pk and linked_variant.held == units

    collect_payment(order, actor=seller)
    item.refresh_from_db()
    assert item.available_quantity == 8 - units
    record_return(order, actor=seller, rows=[{"line_id": order.lines.get().pk, "quantity": 1,
                                             "disposition": "restock"}])
    item.refresh_from_db()
    assert item.available_quantity == 8
    linked_variant.refresh_from_db()
    assert linked_variant.linked_product_id == item.pk and linked_variant.held == 0
    switch(space, "shop.consumable_link")
    assert product_payload(space, product)["variants"][0]["sold_out"] is False
    assert priced_basket(space, [line(variant)]).items[0][0].pk == variant.pk
