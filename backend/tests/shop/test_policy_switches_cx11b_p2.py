"""Routeless shop policies affect quotes, stock disclosure and commitment, retaining rows."""
from decimal import Decimal

import pytest
from django.db import connection

from apps.payments.models import MakerspacePaymentSettings, MakerspaceTaxSettings, PriceDiscount
from apps.shop.checkout import Buyer, place_online_order
from apps.shop.errors import ShopRefused
from apps.makerspaces.guards import SurfaceOff
from apps.shop.models import ShopCheckoutHold
from apps.shop.pricing import priced_basket
from apps.shop.public import product_payload
from apps.shop.reorder import stock_fell
from tests.modules.switch_matrix_object_helpers import retained
from tests.modules.test_switch_matrix_objects_rest_isolation import rolled_back
from tests.payments.switch_helpers_cx11b_p2 import _no_write, domain_rows, no_policy_writes, read_policy_cycle, switch
from tests.shop.helpers import line, manager, member, product, shop_space

pytestmark = [pytest.mark.django_db, pytest.mark.area_shop, pytest.mark.area_payments_ledger]


@pytest.mark.parametrize("key", ["shop.member_prices", "shop.public_stock", "shop.order_limits", "shop.bundles",
                                 "shop.tax", "billing.tax", "charges.discounts", "charges.pricing"])
def test_retained_catalogue_policies_change_the_real_quote_or_public_projection(key):
    space = shop_space("p2-shop-policy", "shop.member_prices", "shop.public_stock", "shop.order_limits",
        "shop.bundles", "shop.tax", "billing.tax", "charges.discounts", "charges.pricing", "shop.online")
    seller, buyer = manager(space), member(space)
    row, variant = product(space, seller, price="100.00", stock=8, show_exact_stock=True, max_per_order=1)
    payment_settings = MakerspacePaymentSettings.for_makerspace(space)
    payment_settings.default_currency = "inr"
    payment_settings.save()
    tax = MakerspaceTaxSettings.objects.create(makerspace=space, mode="single", tax_name="VAT", rate_bps=500)
    discount = PriceDiscount.objects.create(makerspace=space, name="Members", audience="all_members",
        percent_bps=1000, domains=["shop"], created_by=seller)
    objects = {"product": row, "variant": variant, "tax": tax, "discount": discount}
    if key in {"shop.member_prices", "charges.discounts"}:
        read, on, off = lambda: priced_basket(space, [line(variant)], person=buyer).quote.total, Decimal("90"), Decimal("100")
    elif key == "shop.public_stock":
        read = lambda: product_payload(space, row)["variants"][0]["stock_count"]
        on, off = 8, None
    elif key == "shop.order_limits":
        def read():
            try:
                priced_basket(space, [line(variant, 2)])
            except ShopRefused as error:
                return error.status_code, error.code
            return "allowed"
        on, off = (400, "per_order_limit"), "allowed"
    elif key in {"shop.tax", "billing.tax"}:
        def read():
            basket = priced_basket(space, [line(variant)])
            return basket.quote.currency, basket.quote.total, basket.tax
        on = ("inr", Decimal("100.00"), [{"rate_bps": 500, "hsn_code": "",
            "taxable": Decimal("95.24"), "tax": Decimal("4.76"), "gross": Decimal("100.00")}])
        off = ("inr", Decimal("100.00"), None)
    elif key == "charges.pricing":
        from tests.payments.pricing.helpers import rate
        from apps.payments.pricing import quote
        rate_row = rate(space, "membership", dues="25.00")
        objects["rate"] = rate_row
        read, on, off = lambda: quote(space, "membership").total, Decimal("25"), Decimal("0")
    else:
        from apps.shop.services_catalogue import save_product
        kit = save_product(space, {"kind": "kit", "name": "Retained kit", "bundle_mode": True, "price": 10,
            "components": [{"variant_id": variant.pk, "quantity": 2}]}, actor=seller)
        kit_variant = kit.variants.get()
        objects.update(kit=kit, kit_variant=kit_variant)
        read = lambda: [(part.pk, count) for part, count in priced_basket(space, [line(kit_variant)]).stock_pairs()]
        on, off = [(variant.pk, 2)], [(kit_variant.pk, 1)]
    read_policy_cycle(space, objects, key, read, on, off)


@pytest.mark.parametrize("key", ["shop.holds", "shop", "shop.online"])
def test_hold_policy_retains_old_commitments_and_restores_new_commitments(key):
    space = shop_space("p2-hold", "shop.online", "shop.holds")
    seller, buyer = manager(space), member(space)
    row, variant = product(space, seller, price="10", stock=8)
    person = Buyer(buyer, "Retained buyer", buyer.email, buyer)
    first, payment = place_online_order(space, person, {"lines": [line(variant)]})
    objects = {"product": row, "variant": variant, "order": first, "payment": payment}
    before = retained(objects)
    original = switch(space, key)
    if key == "shop.holds":
        with rolled_back():
            second, second_payment = place_online_order(space, person, {"lines": [line(variant)]})
            assert ShopCheckoutHold.objects.filter(order=second).count() == 0
            assert (second_payment.provider, second_payment.amount) == ("unclaimed", Decimal("10"))
    else:
        rows = domain_rows()
        with connection.execute_wrapper(_no_write), pytest.raises(SurfaceOff if key == "shop" else ShopRefused) as error:
            place_online_order(space, person, {"lines": [line(variant)]})
        assert (error.value.status_code, str(error.value.detail["code"])) == (404, "module_disabled" if key == "shop" else "feature_off")
        assert domain_rows() == rows
    assert retained(objects) == before
    assert ShopCheckoutHold.objects.get(order=first).released_at is None
    switch(space, key, original=original)
    second, second_payment = place_online_order(space, person, {"lines": [line(variant)]})
    assert ShopCheckoutHold.objects.get(order=second).quantity == 1
    assert (second_payment.provider, second_payment.amount) == ("unclaimed", Decimal("10"))


@pytest.mark.parametrize("key", ["shop.reorder", "shop"])
def test_reorder_worker_is_inert_off_and_creates_one_retained_procurement_draft_on(key):
    from apps.procurement.models import ToBuyItem
    space = shop_space("p2-reorder", "shop.reorder", "inventory.tobuy")
    row, variant = product(space, manager(space), stock=1)
    variant.reorder_point = 2
    variant.save(update_fields=["reorder_point"])
    before, rows = retained({"product": row, "variant": variant}), domain_rows()
    original = switch(space, key)
    with no_policy_writes():
        assert stock_fell(variant.pk) is None
    assert domain_rows() == rows
    assert retained({"product": row, "variant": variant}) == before
    switch(space, key, original=original)
    item = stock_fell(variant.pk)
    assert (item.quantity, item.status, item.source_shop_variant_id) == (2, "requested", variant.pk)
    assert stock_fell(variant.pk) is False
    assert ToBuyItem.objects.filter(source_shop_variant=variant).count() == 1
    from apps.audit.models import AuditLog
    assert AuditLog.objects.filter(makerspace=space, action="procurement.auto_tobuy_created").count() == 1
