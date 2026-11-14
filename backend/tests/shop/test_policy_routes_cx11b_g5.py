"""The same HTTP callers independently consume policy switches, not invented URL gates."""
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.payments.models import MakerspaceTaxSettings, PriceDiscount
from apps.shop.models import ShopOrder, ShopProduct
from apps.shop.orders_core import order_payment
from apps.shop.services_cash import open_cash
from tests.events.checkin_helpers import make_event
from tests.payments.route_support_cx11b_g5 import cycle, hidden, no_domain_writes, send, success, world
from tests.modules.switch_matrix_object_helpers import response_pair
from tests.modules.test_switch_matrix_objects_rest_isolation import rolled_back
from tests.modules.test_switch_matrix_objects_rest_support import domain_rows, switch
from tests.shop.helpers import line
from tests.shop.route_fixtures_cx11b_g5 import seed

pytestmark = [pytest.mark.django_db, pytest.mark.area_shop, pytest.mark.area_payments_ledger]
SALES = ("public-shop-quote", "public-shop-orders", "admin-shop-pos-quote", "admin-shop-pos-sale")
CASES = [(name, key, native) for name in SALES for key in (
    "shop.member_prices", "charges.discounts", "charges.pricing", "shop.tax", "billing.tax",
    *(("shop.holds",) if name == "public-shop-orders" else ())) for native in (False, True)]


def route(s, name):
    public = name.startswith("public-")
    kwargs = {"makerspace_slug": s.space.slug} if public else {"makerspace_id": s.space.pk}
    body = {"lines": [line(s.variant)]}
    if not public:
        body["member_id"] = s.buyer.pk
    if name.endswith("pos-sale"):
        open_cash(s.space, actor=s.actor, opening_float="10")
        body.update(method="cash", reference="G5-POLICY")
    return reverse(name, kwargs=kwargs), body, s.buyer_client if public else s.client


def mutation(name):
    return name in {"public-shop-orders", "admin-shop-pos-sale"}


def audit_for(name):
    return ("shop.order_placed",) if name == "public-shop-orders" else ("shop.pos_sale",) if name.endswith("pos-sale") else ()


@pytest.mark.parametrize("name,key,native", CASES)
def test_quote_and_sale_routes_use_each_price_tax_and_hold_policy_and_keep_frozen_rows(name, key, native):
    s = seed(native)
    discount = key in {"shop.member_prices", "charges.discounts", "charges.pricing"}
    tax = key in {"shop.tax", "billing.tax"}
    if discount:
        s.space.enabled_features += ["charges.discounts", "charges.pricing"]
        s.space.save(update_fields=["enabled_features"])
        PriceDiscount.objects.create(makerspace=s.space, name="G5 member price", audience="all_members",
            percent_bps=1000, domains=["shop"], created_by=s.actor)
    if tax:
        s.space.enabled_features += ["billing.tax"]
        s.space.save(update_fields=["enabled_features"])
        MakerspaceTaxSettings.objects.create(makerspace=s.space, mode="single", tax_name="VAT", rate_bps=500,
            prices_include_tax=False)
    url, body, caller = route(s, name)
    def result(response):
        # Policy switches change NEW quotes; the restored command freezes its on-state price.
        total = Decimal("11.25") if discount and not w.disabled else Decimal("12.50")
        tax_amount = Decimal("0.60") if tax else Decimal("0")
        due = total
        if tax and w.disabled:
            tax_amount = Decimal("0.63") if key == "shop.tax" else Decimal("0")
            due += tax_amount
        if mutation(name):
            row_id = response.data["order"]["id"] if name == "public-shop-orders" else response.data["id"]
            order = ShopOrder.objects.get(pk=row_id)
            payment = order_payment(order)
            assert (order.total, order.amount_due, payment.amount) == (total, due, due)
            assert order.lines.get().line_total == total
            assert payment.pricing_snapshot["digest"] == order.digest
            if tax:
                if key == "billing.tax" and w.disabled:
                    assert payment.tax_snapshot is None
                else:
                    assert payment.tax_snapshot["rate_bps"] == 500
                    assert Decimal(payment.tax_snapshot["figures"]["tax"]) == tax_amount
                    assert Decimal(payment.tax_snapshot["figures"]["gross"]) == due
                    assert Decimal(payment.tax_snapshot["figures"]["taxable"]) == due - tax_amount
            if name == "public-shop-orders":
                expected = 0 if key == "shop.holds" and w.disabled else 1
                assert order.holds.count() == expected
            else:
                assert payment.manual_settlements.get().amount == due
        else:
            assert (Decimal(response.data["total"]), Decimal(response.data["amount_due"]),
                    Decimal(response.data["tax_total"])) == (total, due, tax_amount)
            assert response.data["lines"][0]["variant_id"] == s.variant.pk
    w = world(s.space, caller, url, "POST", body, (201, None) if mutation(name) else (200, None),
        audit_for(name), result, probes=[hidden(s.foreign)] if name.startswith("admin-") else (), audit_prefix="shop.")
    cycle(w, key)


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("name", ["public-shop-products", "public-shop-product"])
def test_each_public_product_read_uses_exact_stock_policy_without_discarding_stock(native, name):
    s = seed(native)
    ShopProduct.objects.filter(pk=s.product.pk).update(show_exact_stock=True)
    kwargs = {"makerspace_slug": s.space.slug}
    if name.endswith("product"):
        kwargs["product_slug"] = s.product.slug
    def result(response):
        row = response.data if name.endswith("product") else response.data["results"][0]
        assert row["id"] == s.product.pk
        assert (row["variants"][0]["stock_count"], row["variants"][0]["stock_label"]) == (
            (None, None) if w.disabled else (8, "in_stock"))
        assert type(s.variant).objects.get(pk=s.variant.pk).on_hand == 8
    w = world(s.space, s.buyer_client, reverse(name, kwargs=kwargs), check=result)
    cycle(w, "shop.public_stock")


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("name", SALES)
def test_each_quote_or_sale_refuses_disabled_inventory_link_before_committing_stock(native, name):
    from apps.inventory.models import InventoryProduct
    from apps.shop.services_catalogue import save_product
    s = seed(native)
    inventory = InventoryProduct.objects.create(makerspace=s.space, name="G5 shared resin", is_consumable=True,
        total_quantity=8, available_quantity=8)
    linked = save_product(s.space, {"name": "G5 resin", "variants": [{"price": "12.50", "linked_product_id": inventory.pk}]}, actor=s.actor)
    s.variant = linked.variants.get()
    url, body, caller = route(s, name)
    def result(response):
        inventory.refresh_from_db()
        if mutation(name):
            pk = response.data["order"]["id"] if name == "public-shop-orders" else response.data["id"]
            order = ShopOrder.objects.get(pk=pk)
            assert order.lines.get().variant_id == s.variant.pk
            assert order_payment(order).amount == Decimal("12.50")
            if name == "public-shop-orders":
                assert order.holds.get().variant_id == s.variant.pk
                assert inventory.available_quantity == 8
            else:
                assert inventory.available_quantity == 7
        else:
            assert Decimal(response.data["total"]) == Decimal("12.50") and inventory.available_quantity == 8
    w = world(s.space, caller, url, "POST", body, (201, None) if mutation(name) else (200, None),
        audit_for(name), result, probes=[hidden(s.foreign)] if name.startswith("admin-") else (), audit_prefix="shop.")
    cycle(w, "shop.consumable_link", (404, "feature_off"))


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["events", "shop.event_pickup"])
def test_online_order_event_pickup_independently_needs_events_and_pickup_capability(native, key):
    s = seed(native)
    event = make_event(s.space)
    url, body, caller = route(s, "public-shop-orders")
    body.update(pickup_at="event", pickup_event_id=event.pk)
    def result(response):
        order = ShopOrder.objects.get(pk=response.data["order"]["id"])
        assert (order.pickup_at, order.pickup_event_id, order.buyer_id) == ("event", event.pk, s.buyer.pk)
        assert order_payment(order).amount == Decimal("12.50") and order.holds.get().quantity == 1
    cycle(world(s.space, caller, url, "POST", body, (201, None), ("shop.order_placed",), result,
                audit_prefix="shop."), key, (404, "feature_off"))


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("name", ["public-shop-orders", "admin-shop-pos-sale"])
def test_each_sale_freezes_the_bundle_policy_and_commits_the_exact_stock_source(native, name):
    from apps.shop.services_catalogue import move_stock, save_product
    s = seed(native)
    component = s.variant
    kit = save_product(s.space, {"kind": "kit", "name": "G5 bundle", "bundle_mode": True, "price": "12.50",
        "components": [{"variant_id": component.pk, "quantity": 2}]}, actor=s.actor)
    s.variant = kit.variants.get()
    move_stock(s.variant, actor=s.actor, kind="restock", quantity=3, reason="G5 kit seed")
    url, body, caller = route(s, name)
    def result(response):
        order_id = response.data["order"]["id"] if name == "public-shop-orders" else response.data["id"]
        order = ShopOrder.objects.get(pk=order_id)
        assert order.pricing_snapshot["bundles"] is (not w.disabled)
        component.refresh_from_db()
        kit_variant = type(s.variant).objects.get(pk=s.variant.pk)
        if name == "public-shop-orders":
            assert list(order.holds.values_list("variant_id", "quantity")) == [
                (s.variant.pk, 1) if w.disabled else (component.pk, 2)]
            assert (component.on_hand, kit_variant.on_hand) == (8, 3)
        else:
            assert (component.on_hand, kit_variant.on_hand) == ((8, 2) if w.disabled else (6, 3))
        assert order_payment(order).amount == Decimal("12.50")
    w = world(s.space, caller, url, "POST", body, (201, None), audit_for(name), result, audit_prefix="shop.")
    cycle(w, "shop.bundles")


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("name", SALES)
def test_every_basket_caller_keeps_the_per_product_limit_rule_and_restores_it(native, name):
    s = seed(native)
    ShopProduct.objects.filter(pk=s.product.pk).update(max_per_order=1)
    url, body, caller = route(s, name)
    def result(response):
        quantity = w.body["lines"][0]["quantity"]
        expected = Decimal("12.50") * quantity
        if mutation(name):
            row_id = response.data["order"]["id"] if name == "public-shop-orders" else response.data["id"]
            order = ShopOrder.objects.get(pk=row_id)
            assert (order.lines.get().quantity, order_payment(order).amount) == (quantity, expected)
        else:
            assert Decimal(response.data["total"]) == expected
    w = world(s.space, caller, url, "POST", body, (201, None) if mutation(name) else (200, None),
        audit_for(name), result, audit_prefix="shop.")
    with rolled_back():
        success(w)  # Valid on-state quantity, with an actual quote/order/receipt.
    body["lines"][0]["quantity"] = 2
    before = domain_rows()
    with no_domain_writes():
        assert response_pair(send(w)) == (400, "per_order_limit")
    assert domain_rows() == before
    original = switch(s.space, "shop.order_limits")
    with rolled_back():
        success(w)  # Off removes this policy only: exactly two units and the 25.00 charge.
    assert domain_rows() == before
    switch(s.space, "shop.order_limits", original=original)
    with no_domain_writes():
        assert response_pair(send(w)) == (400, "per_order_limit")
    assert domain_rows() == before
    body["lines"][0]["quantity"] = 1
    success(w)


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("name", ["admin-shop-pos-sale", "admin-shop-order-take-payment"])
def test_each_cash_sale_keeps_its_receipt_and_independently_associates_the_cash_session(native, name):
    from apps.shop.checkout import Buyer, place_online_order
    s = seed(native)
    cash = open_cash(s.space, actor=s.actor, opening_float="10")
    if name.endswith("pos-sale"):
        url = reverse(name, kwargs={"makerspace_id": s.space.pk})
        body = {"lines": [line(s.variant)], "method": "cash", "reference": "G5-CASH-POLICY"}
        audit, on = ("shop.pos_sale",), (201, None)
    else:
        order, _ = place_online_order(s.space, Buyer(s.buyer, "Buyer", "buyer@example.test", s.buyer), {"lines": [line(s.variant)]})
        url = reverse(name, kwargs={"pk": order.pk})
        body = {"method": "cash", "reference": "G5-CASH-POLICY"}
        audit, on = ("shop.order_paid", "shop.order_paid_at_desk"), (200, None)
    def result(response):
        saved = ShopOrder.objects.get(pk=response.data["id"])
        assert saved.cash_session_id == (None if w.disabled else cash.pk)
        assert saved.status == "collected" and type(s.variant).objects.get(pk=s.variant.pk).on_hand == 7
        payment = order_payment(saved)
        assert payment.amount == Decimal("12.50") and payment.status == "paid_offline"
        assert payment.manual_settlements.get().reference == "G5-CASH-POLICY"
    w = world(s.space, s.client, url, "POST", body, on, audit, result, probes=[hidden(s.foreign)], audit_prefix="shop.")
    cycle(w, "shop.cash_up")


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
def test_cash_close_independently_requires_a_second_person_when_maker_checker_is_on(native):
    from apps.shop.models import ShopCashSession
    s = seed(native)
    s.space.enabled_features += ["billing.maker_checker"]
    s.space.save(update_fields=["enabled_features"])
    cash = open_cash(s.space, actor=s.actor, opening_float="10")
    def result(response):
        saved = ShopCashSession.objects.get(pk=cash.pk)
        assert (saved.status, saved.closed_by_id, saved.confirmed_by_id) == (
            "closed" if w.disabled else "closing", s.actor.pk, s.actor.pk if w.disabled else None)
        assert saved.expected_cash == saved.counted_cash == Decimal("10") and saved.variance == 0
    w = world(s.space, s.client, reverse("admin-shop-cash-session-close", kwargs={"pk": cash.pk}),
        "POST", {"counted_cash": "10.00"}, audit=("shop.cash_session_close_proposed",), check=result,
        probes=[hidden(s.foreign)])
    # The owning audit changes with the policy; both branches keep the second-person rule intact.
    original_check = w.check
    def check(response):
        original_check(response)
        w.audit = ("shop.cash_session_closed" if w.disabled else "shop.cash_session_close_proposed",)
    w.check = check
    cycle(w, "billing.maker_checker")
