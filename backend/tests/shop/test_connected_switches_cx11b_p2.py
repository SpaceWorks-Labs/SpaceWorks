"""Shop pickup/link policies consume real event and inventory rows; quantities stay owned by availability."""
import pytest

from apps.inventory.models import InventoryProduct
from apps.shop.checkout import pickup_choice
from apps.shop.errors import ShopRefused
from apps.shop.pricing import priced_basket
from apps.shop.services_catalogue import save_product
from tests.events.checkin_helpers import make_event
from tests.payments.switch_helpers_cx11b_p2 import read_policy_cycle
from tests.shop.helpers import line, manager, shop_space, switch

pytestmark = [pytest.mark.django_db, pytest.mark.area_shop, pytest.mark.area_payments_ledger]


@pytest.mark.parametrize("key", ["shop.event_pickup", "events"])
def test_event_pickup_policy_keeps_event_and_refuses_selection_off(key):
    space = shop_space("p2-shop-event", "shop.event_pickup")
    switch(space, modules=("events",))
    event = make_event(space)
    def read():
        try:
            kind, selected = pickup_choice(space, {"pickup_at": "event", "pickup_event_id": event.pk})
            return kind, selected.pk
        except ShopRefused as error:
            return error.status_code, error.code
    read_policy_cycle(space, {"event": event}, key, read, ("event", event.pk), (404, "feature_off"))


def test_inventory_consumable_link_refuses_new_baskets_off_and_retains_one_stock_source():
    space = shop_space("p2-shop-link", "shop.consumable_link")
    actor = manager(space)
    stock = InventoryProduct.objects.create(makerspace=space, name="Retained resin", is_consumable=True,
        available_quantity=8, total_quantity=8)
    row = save_product(space, {"name": "Resin bottle", "variants": [{"name": "One litre", "price": 30,
        "linked_product_id": stock.pk}]}, actor=actor)
    variant = row.variants.get()
    from apps.payments.models import MakerspacePaymentSettings
    MakerspacePaymentSettings.objects.get_or_create(makerspace=space)
    def read():
        try:
            basket = priced_basket(space, [line(variant)])
            return [(source.linked_product_id, quantity) for source, quantity in basket.stock_pairs()]
        except ShopRefused as error:
            return error.status_code, error.code
    read_policy_cycle(space, {"stock": stock, "product": row, "variant": variant}, "shop.consumable_link",
        read, [(stock.pk, 1)], (404, "feature_off"))
