"""Decision 509: charges off refuses sales; catalogue, stock and existing debts remain."""
from decimal import Decimal

import pytest

from apps.audit.models import AuditLog
from apps.payments.models import ManualSettlement, Payment
from apps.shop.models import ShopOrder

from .helpers import client, line, member, module_off, product, shop_manager, shop_space, switch

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("disabled", ["charges.enabled", "charges.shop"])
@pytest.mark.parametrize("surface", ["online", "desk"])
def test_charges_off_refuses_new_sales_without_money_stock_or_audit_writes(disabled, surface):
    space = shop_space("cx7-charges-off", "shop.online", "shop.cash_up", "shop.holds")
    seller = shop_manager(space)
    buyer = member(space)
    _, variant = product(space, seller, price="12.50", stock=3)
    switch(space, disabled, on=False)
    body = {"lines": [line(variant, 2)], "method": "cash"}
    public = f"/api/v1/public/m/{space.slug}/shop/"
    staff = f"/api/v1/admin/makerspaces/{space.pk}/shop/"
    caller, url = (client(buyer), f"{public}orders/") if surface == "online" else (
        client(seller), f"{staff}pos/sale/")
    quote = caller.post(f"{public}quote/" if surface == "online" else f"{staff}pos/quote/",
                        body, format="json")
    assert quote.status_code == 404
    assert quote.json()["code"] == "charges_off"
    assert quote.json()["detail"] == "This shop is not taking orders right now."
    for _ in range(2):
        response = caller.post(url, body, format="json", HTTP_IDEMPOTENCY_KEY="cx7-refused-order")
        assert response.status_code == 409
        assert response.json()["code"] == "charges_off"
        assert response.json()["detail"] == "This shop is not taking orders right now."
    variant.refresh_from_db()
    assert (variant.on_hand, variant.held, variant.price) == (3, 0, Decimal("12.50"))
    assert ShopOrder.objects.filter(makerspace=space).count() == 0
    assert Payment.objects.filter(makerspace=space).count() == 0
    assert ManualSettlement.objects.filter(payment__makerspace=space).count() == 0
    assert AuditLog.objects.filter(makerspace=space, action__in=["shop.order_placed", "shop.pos_sale"]).count() == 0


@pytest.mark.parametrize("surface", ["public", "staff"])
def test_duplicate_lines_respect_the_merged_quantity_boundary(surface):
    space = shop_space("cx7-quantity", "shop.online")
    seller = shop_manager(space)
    _, variant = product(space, seller, stock=1000)
    caller, url = (client(), f"/api/v1/public/m/{space.slug}/shop/quote/") if surface == "public" else (
        client(seller), f"/api/v1/admin/makerspaces/{space.pk}/shop/pos/quote/")
    maximum = caller.post(url, {"lines": [line(variant, 998), line(variant, 1)]}, format="json")
    assert maximum.status_code == 200
    assert Decimal(maximum.json()["lines"][0]["quantity"]) == 999
    refused = caller.post(url, {"lines": [line(variant, 999), line(variant, 1)]}, format="json")
    assert refused.status_code == 400
    assert refused.json()["code"] == "variant_invalid"
    assert refused.json()["detail"] == "Choose a quantity between 1 and 999."
    assert ShopOrder.objects.filter(makerspace=space).count() == 0


def test_charges_off_preserves_module_switches_stock_and_stored_prices():
    space = shop_space("cx7-roundtrip", "shop.online")
    seller = shop_manager(space)
    row, variant = product(space, seller, price="7.00", stock=1)
    switch(space, "charges.enabled", on=False)
    url = f"/api/v1/public/m/{space.slug}/shop/quote/"
    body = {"lines": [line(variant)]}
    charges_off = client().post(url, body, format="json")
    assert charges_off.status_code == 404
    assert charges_off.json()["code"] == "charges_off"
    module_off(space)
    refused = client().post(url, body, format="json")
    assert refused.status_code == 404
    assert refused.json()["code"] == "shop_closed"
    switch(space, "charges.enabled", modules=("shop",))
    restored = client().post(url, body, format="json")
    assert restored.status_code == 200
    assert Decimal(restored.json()["total"]) == Decimal("7.00")
    variant.refresh_from_db()
    assert variant.price == Decimal("7.00")
    assert variant.on_hand == 1
    assert row.variants.count() == 1


def test_paid_order_refuses_insufficient_stock_without_partial_writes():
    space = shop_space("cx7-free-stock", "shop.online")
    seller = shop_manager(space)
    _, variant = product(space, seller, stock=1)
    response = client(member(space)).post(f"/api/v1/public/m/{space.slug}/shop/orders/",
                                         {"lines": [line(variant, 2)]}, format="json")
    assert response.status_code == 409
    assert response.json()["code"] == "out_of_stock"
    assert ShopOrder.objects.filter(makerspace=space).count() == 0
    assert Payment.objects.filter(makerspace=space).count() == 0
    variant.refresh_from_db()
    assert variant.on_hand == 1


def test_saved_price_change_after_charges_roundtrip_requires_confirmation():
    space = shop_space("cx7-free-digest", "shop.online")
    seller = shop_manager(space)
    _, variant = product(space, seller, price="4.00")
    base = f"/api/v1/public/m/{space.slug}/shop/"
    body = {"lines": [line(variant)]}
    saved_quote = client().post(f"{base}quote/", body, format="json")
    assert saved_quote.status_code == 200
    assert Decimal(saved_quote.json()["total"]) == Decimal("4.00")
    switch(space, "charges.enabled", on=False)
    from apps.shop.models import ShopVariant
    ShopVariant.objects.filter(pk=variant.pk).update(price=Decimal("5.00"))
    switch(space, "charges.enabled")
    response = client(member(space)).post(f"{base}orders/",
        {**body, "quote_digest": saved_quote.json()["digest"]}, format="json")
    assert response.status_code == 409
    assert response.json()["code"] == "price_changed"
    assert ShopOrder.objects.filter(makerspace=space).count() == 0
    assert Payment.objects.filter(makerspace=space).count() == 0


def test_selling_preserves_member_only_rules_and_per_order_limits():
    space = shop_space("cx7-free-rules", "shop.online", "shop.member_prices", "shop.order_limits")
    seller = shop_manager(space)
    _, variant = product(space, seller, members_only=True, max_per_order=1)
    base = f"/api/v1/public/m/{space.slug}/shop/quote/"
    denied = client().post(base, {"lines": [line(variant)]}, format="json")
    assert denied.status_code == 403
    assert denied.json()["code"] == "member_only"
    buyer = client(member(space))
    allowed = buyer.post(base, {"lines": [line(variant)]}, format="json")
    assert allowed.status_code == 200
    denied = buyer.post(base, {"lines": [line(variant, 2)]}, format="json")
    assert denied.status_code == 400
    assert denied.json()["code"] == "per_order_limit"
    switch(space, "shop.order_limits", on=False)
    allowed = buyer.post(base, {"lines": [line(variant, 2)]}, format="json")
    assert allowed.status_code == 200
    switch(space, "shop.order_limits")
    restored = buyer.post(base, {"lines": [line(variant, 2)]}, format="json")
    assert restored.status_code == 400
    assert restored.json()["code"] == "per_order_limit"


def test_existing_paid_order_still_settles_offline_after_charges_are_off():
    space = shop_space("cx7-debt-kept", "shop.online", "shop.holds")
    seller = shop_manager(space)
    _, variant = product(space, seller, price="6.50", stock=2)
    placed = client(member(space)).post(f"/api/v1/public/m/{space.slug}/shop/orders/",
                                        {"lines": [line(variant)]}, format="json")
    assert placed.status_code == 201
    order_id = placed.json()["order"]["id"]
    switch(space, "charges.enabled", on=False)
    settled = client(seller).post(f"/api/v1/admin/shop/orders/{order_id}/take-payment/",
                                  {"method": "upi", "reference": "CX7-RECEIPT"}, format="json")
    assert settled.status_code == 200
    assert settled.json()["status"] == "collected"
    payment = Payment.objects.get(makerspace=space)
    assert payment.amount == Decimal("6.50")
    assert payment.status == "paid_offline"
    receipt = ManualSettlement.objects.get(payment=payment)
    assert receipt.method == "upi"
    assert receipt.reference == "CX7-RECEIPT"
    variant.refresh_from_db()
    assert (variant.on_hand, variant.held) == (1, 0)


@pytest.mark.parametrize("surface", ["online", "desk"])
def test_new_sale_accepts_merged_999_and_refuses_1000_before_writes(surface):
    space = shop_space("cx7-sale-quantity", "shop.online", "shop.holds")
    seller = shop_manager(space)
    _, variant = product(space, seller, price="0.01", stock=2000)
    caller, url = (client(member(space)), f"/api/v1/public/m/{space.slug}/shop/orders/") if surface == "online" else (
        client(seller), f"/api/v1/admin/makerspaces/{space.pk}/shop/pos/sale/")
    maximum = caller.post(url, {"lines": [line(variant, 998), line(variant, 1)], "method": "upi"}, format="json")
    assert maximum.status_code == 201
    order = ShopOrder.objects.get(makerspace=space)
    assert order.lines.get().quantity == 999
    assert order.total == Decimal("9.99")
    before = (Payment.objects.filter(makerspace=space).count(), variant.movements.count())
    refused = caller.post(url, {"lines": [line(variant, 999), line(variant, 1)], "method": "upi"}, format="json")
    assert refused.status_code == 400
    assert refused.json()["code"] == "variant_invalid"
    assert ShopOrder.objects.filter(makerspace=space).count() == 1
    assert (Payment.objects.filter(makerspace=space).count(), variant.movements.count()) == before


@pytest.mark.parametrize("disabled", ["charges.enabled", "charges.shop"])
def test_kernel_keeps_saved_price_when_sales_are_disabled(disabled):
    from apps.payments.pricing import quote
    space = shop_space("cx7-kernel-price")
    seller = shop_manager(space)
    _, variant = product(space, seller, price="12.50")
    switch(space, disabled, on=False)
    saved = quote(space, "shop", params={"lines": [(variant, 2)]})
    assert saved.total == Decimal("25.00")
    assert saved.lines[0].unit_amount == Decimal("12.50")
    assert ShopOrder.objects.filter(makerspace=space).count() == 0


@pytest.mark.parametrize("surface", ["online", "desk"])
def test_charges_on_without_online_rail_keeps_offline_receipt_and_replay(surface):
    space = shop_space("cx7-offline-sale", "shop.online", "shop.holds")
    seller = shop_manager(space)
    _, variant = product(space, seller, price="6.50", stock=2)
    body = {"lines": [line(variant)], "method": "cash", "reference": "CX7-CASH"}
    if surface == "desk":
        response = client(seller).post(f"/api/v1/admin/makerspaces/{space.pk}/shop/pos/sale/", body, format="json")
        assert response.status_code == 201
        order_id = response.json()["id"]
    else:
        url = f"/api/v1/public/m/{space.slug}/shop/orders/"
        caller = client(member(space))
        response = caller.post(url, body, format="json", HTTP_IDEMPOTENCY_KEY="cx7-offline-sale")
        assert response.status_code == 201
        assert response.json()["checkout_url"] == ""
        order_id = response.json()["order"]["id"]
        replay = caller.post(url, body, format="json", HTTP_IDEMPOTENCY_KEY="cx7-offline-sale")
        assert replay.status_code == 201
        assert replay.json()["order"]["id"] == order_id
        settled = client(seller).post(f"/api/v1/admin/shop/orders/{order_id}/take-payment/", body, format="json")
        assert settled.status_code == 200
        assert settled.json()["status"] == "collected"
    payment = Payment.objects.get(makerspace=space)
    assert (payment.amount, payment.provider, payment.status) == (Decimal("6.50"), "unclaimed", "paid_offline")
    receipt = ManualSettlement.objects.get(payment=payment)
    assert (receipt.method, receipt.reference) == ("cash", "CX7-CASH")
    assert ShopOrder.objects.filter(makerspace=space).count() == 1
    assert ShopOrder.objects.get(pk=order_id).status == "collected"
    variant.refresh_from_db()
    assert (variant.on_hand, variant.held) == (1, 0)
