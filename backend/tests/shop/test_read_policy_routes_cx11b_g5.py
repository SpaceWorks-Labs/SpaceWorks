"""Public reads expose exact policy effects while preserving their seeded catalogue."""
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.shop.models import ShopEventOffer, ShopProduct
from tests.events.checkin_helpers import make_event
from tests.payments.route_support_cx11b_g5 import cycle, world
from tests.payments_rail.ports_cx11b_g5 import configure
from tests.shop.route_fixtures_cx11b_g5 import seed

pytestmark = [pytest.mark.django_db, pytest.mark.area_shop]
READS = ("public-shop-products", "public-shop-product", "public-shop-event-offers")
SUMMARY_KEYS = ("shop.guest_checkout", "shop.member_prices", "shop.returns", "shop.holds",
                "events", "shop.event_pickup", "payments", "payments.enabled", "payments.shop",
                "charges.enabled", "charges.shop")


def reader(s, name, product=None):
    product = product or s.product
    kwargs = {"makerspace_slug": s.space.slug}
    if name == "public-shop-product":
        kwargs["product_slug"] = product.slug
    if name == "public-shop-event-offers":
        event = make_event(s.space)
        ShopEventOffer.objects.create(makerspace=s.space, event=event, variant=product.variants.get())
        kwargs["public_token"] = event.public_token
    return reverse(name, kwargs=kwargs)


def payload(response, name):
    return response.data["results"][0] if name.endswith("products") else (
        response.data["products"][0] if name.endswith("offers") else response.data)


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", SUMMARY_KEYS)
def test_public_summary_independently_reports_every_payment_pickup_and_shop_policy(native, key, monkeypatch):
    s = seed(native)
    s.space.enabled_modules += ["payments"]
    s.space.enabled_features += ["payments.enabled", "payments.shop"]
    s.space.save(update_fields=["enabled_modules", "enabled_features"])
    configure(s, monkeypatch)
    event = make_event(s.space)
    def result(response):
        data = response.data
        disabled = w.disabled
        assert data["name"] == s.space.name and data["policy_text"] == "G5 retained policy"
        rail_off = disabled and key in {"payments", "payments.enabled", "payments.shop", "charges.enabled", "charges.shop"}
        assert data["pay_online"] is (not rail_off)
        assert data["guest_checkout"] is not (disabled and key == "shop.guest_checkout")
        assert data["member_prices"] is not (disabled and key == "shop.member_prices")
        assert data["returns_days"] == (0 if disabled and key == "shop.returns" else s.policy.returns_window_days)
        assert data["hold_minutes"] == (None if disabled and key == "shop.holds" else 15)
        assert [row["id"] for row in data["pickup_events"]] == (
            [] if disabled and key in {"events", "shop.event_pickup"} else [event.pk])
    # 481/494: these are public policy facts. Anonymous admission is proved by the
    # main route cases; both authenticated transports must see the same facts.
    w = world(s.space, s.buyer_client, reverse("public-shop", kwargs={"makerspace_slug": s.space.slug}), check=result)
    cycle(w, key)


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("name", READS)
@pytest.mark.parametrize("key", ["charges.enabled", "charges.shop", "shop.member_prices", "shop.order_limits", "shop.public_stock"])
def test_each_public_product_payload_keeps_exact_prices_member_limits_and_stock_policy(native, name, key):
    s = seed(native)
    ShopProduct.objects.filter(pk=s.product.pk).update(members_only=True, max_per_order=2, show_exact_stock=True)
    def result(response):
        row = payload(response, name)
        assert row["id"] == s.product.pk and row["variants"][0]["id"] == s.variant.pk
        prices_off = w.disabled and key.startswith("charges.")
        prices = [row["price_from"], row["price_to"], row["variants"][0]["price"]]
        assert [None if value is None else Decimal(value) for value in prices] == [
            None if prices_off else Decimal("12.50")] * 3
        assert row["members_only"] is not (w.disabled and key == "shop.member_prices")
        assert row["max_per_order"] == (None if w.disabled and key == "shop.order_limits" else 2)
        assert (row["variants"][0]["stock_count"], row["variants"][0]["stock_label"]) == (
            (None, None) if w.disabled and key == "shop.public_stock" else (8, "in_stock"))
        assert row["sold_out"] is False and type(s.variant).objects.get(pk=s.variant.pk).on_hand == 8
    w = world(s.space, s.buyer_client, reader(s, name), check=result)
    cycle(w, key)


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("name", READS)
def test_each_public_product_read_hides_disabled_linked_stock_without_touching_inventory(native, name):
    from apps.inventory.models import InventoryProduct
    from apps.shop.services_catalogue import save_product
    s = seed(native)
    stock = InventoryProduct.objects.create(makerspace=s.space, name="G5 retained shared stock", is_consumable=True,
        total_quantity=8, available_quantity=8)
    linked = save_product(s.space, {"name": "G5 linked read", "variants": [
        {"price": "12.50", "linked_product_id": stock.pk}]}, actor=s.actor)
    def result(response):
        data = response.data
        rows = data["results"] if name.endswith("products") else data["products"] if name.endswith("offers") else [data]
        row = next(row for row in rows if row["id"] == linked.pk)
        assert row["sold_out"] is w.disabled
        assert row["variants"][0]["sold_out"] is w.disabled
        assert row["variants"][0]["stock_label"] == ("sold_out" if w.disabled else "in_stock")
        stock.refresh_from_db()
        assert (stock.available_quantity, stock.total_quantity) == (8, 8)
    w = world(s.space, s.buyer_client, reader(s, name, linked), check=result)
    cycle(w, "shop.consumable_link")


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("name", READS)
def test_each_public_product_read_uses_bundle_stock_policy_without_losing_components(native, name):
    from apps.shop.services_catalogue import save_product
    s = seed(native)
    kit = save_product(s.space, {"kind": "kit", "name": "G5 displayed bundle", "bundle_mode": True, "price": "12.50",
        "components": [{"variant_id": s.variant.pk, "quantity": 2}]}, actor=s.actor)
    def result(response):
        data = response.data
        rows = data["results"] if name.endswith("products") else data["products"] if name.endswith("offers") else [data]
        row = next(row for row in rows if row["id"] == kit.pk)
        assert row["sold_out"] is w.disabled  # Component has eight; the kit itself has zero.
        assert row["variants"][0]["stock_label"] == ("sold_out" if w.disabled else "in_stock")
        assert type(s.variant).objects.get(pk=s.variant.pk).on_hand == 8
        assert kit.variants.get().on_hand == 0 and kit.components.get().quantity == 2
    w = world(s.space, s.buyer_client, reader(s, name, kit), check=result)
    cycle(w, "shop.bundles")
