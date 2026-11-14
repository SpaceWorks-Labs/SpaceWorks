"""Real native grants reach the same shop boundaries as browser callers (509).

Only the external attestation provider is stubbed. Registration, password, MFA,
grant validation, tenant header, permissions, quota checks and writes are real.
These prove the API contract; the native apps currently have no shop screen.
"""
from decimal import Decimal
from types import SimpleNamespace

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import DeviceGrant
from apps.payments.models import Payment
from apps.shop.models import ShopOrder
from tests.accounts.account_factories import make_staff
from tests.accounts.mfa_helpers import complete_enrollment
from tests.accounts.mobile_integration_helpers import APP, FIRST, PREFIX, registration

from .helpers import line, product, shop_space, switch

pytestmark = pytest.mark.django_db
PASSWORD = "strong-device-password"


def native_staff_client(space, platform, settings, monkeypatch, *, host=None):
    settings.DEVICE_ATTESTATION_APPS = {}
    setattr(settings, f"DEVICE_{platform.upper()}_ATTESTATION_VERIFY_URL", "https://attest.example.test/verify")
    setattr(settings, f"DEVICE_{platform.upper()}_ATTESTATION_VERIFY_TOKEN", "provider-secret")
    identity = {"platform": platform, "app_id": APP, "environment": "production"}
    registration(**identity)
    actor = make_staff(space, username=f"{space.slug}-{platform}", password=PASSWORD)
    caller = APIClient(**({"HTTP_HOST": host} if host is not None else {}))
    challenge = caller.post("/api/v1/auth/device/attestation-challenge", identity, format="json")
    assert challenge.status_code == 200
    raw = challenge.data["challenge"]
    claims = {**identity, "verified": True, "subject": f"cx7-{platform}", "challenge": raw,
              "signing_identity": PREFIX if platform == "apple" else FIRST}
    monkeypatch.setattr("apps.accounts.attestation_apple.requests.post",
                        lambda *args, **kwargs: SimpleNamespace(status_code=200, json=lambda: claims))
    login = caller.post("/api/v1/auth/device/login", {
        **identity, "username": actor.username, "password": PASSWORD, "authority": "staff",
        "makerspace": space.slug, "challenge": raw, "attestation": {"assertion": "provider-proof"},
    }, format="json")
    assert login.status_code == 200
    assert login.data["mfa_required"] is True
    completed = complete_enrollment(caller, login)
    grant = DeviceGrant.objects.get(user=actor)
    assert (grant.authority, grant.staff_makerspace_id, grant.platform) == ("staff", space.pk, platform)
    caller.credentials(HTTP_AUTHORIZATION=f"Bearer {completed.data['access']}", HTTP_X_MAKERSPACE_ID=str(space.pk))
    return caller, actor


@pytest.mark.parametrize("platform", ["apple", "android"])
def test_native_pos_accepts_merged_max_and_refuses_one_more(platform, settings, monkeypatch):
    space = shop_space("cx7-native-quantity")
    caller, actor = native_staff_client(space, platform, settings, monkeypatch)
    _, variant = product(space, actor, price="0.01", stock=2000)
    url = f"/api/v1/admin/makerspaces/{space.pk}/shop/pos/sale/"
    maximum = caller.post(url, {"lines": [line(variant, 998), line(variant)], "method": "upi"}, format="json")
    assert maximum.status_code == 201
    assert ShopOrder.objects.get(makerspace=space).lines.get().quantity == 999
    refused = caller.post(url, {"lines": [line(variant, 999), line(variant)], "method": "upi"}, format="json")
    assert refused.status_code == 400
    assert refused.json()["code"] == "variant_invalid"
    assert ShopOrder.objects.filter(makerspace=space).count() == 1
    assert Payment.objects.get(makerspace=space).amount == Decimal("9.99")
    variant.refresh_from_db()
    assert (variant.on_hand, variant.held) == (1001, 0)


@pytest.mark.parametrize("platform", ["apple", "android"])
@pytest.mark.parametrize("key", ["charges.enabled", "charges.shop"])
def test_native_charges_off_keeps_catalogue_and_refuses_quote_and_sale(platform, key, settings, monkeypatch):
    space = shop_space("cx7-native-off", "shop.online")
    caller, actor = native_staff_client(space, platform, settings, monkeypatch)
    row, variant = product(space, actor, price="6.50", stock=2)
    switch(space, key, on=False)
    base = f"/api/v1/admin/makerspaces/{space.pk}/shop/"
    body = {"lines": [line(variant)], "method": "cash"}
    listing = caller.get(f"{base}products/")
    assert listing.status_code == 200
    assert listing.json()["results"][0]["id"] == row.pk
    assert listing.json()["results"][0]["variants"][0]["price"] == "6.50"
    quote = caller.post(f"{base}pos/quote/", body, format="json")
    assert quote.status_code == 404
    assert quote.json()["code"] == "charges_off"
    sale = caller.post(f"{base}pos/sale/", body, format="json")
    assert sale.status_code == 409
    assert sale.json()["code"] == "charges_off"
    assert ShopOrder.objects.filter(makerspace=space).count() == 0
    assert Payment.objects.filter(makerspace=space).count() == 0
    variant.refresh_from_db()
    assert (variant.on_hand, variant.held, variant.price) == (2, 0, Decimal("6.50"))


@pytest.mark.parametrize("platform", ["browser", "apple", "android"])
def test_catalogue_quota_accepts_last_product_and_refuses_next(platform, settings, monkeypatch):
    from .helpers import client, shop_manager
    space = shop_space("cx7-native-products")
    caller = client(shop_manager(space)) if platform == "browser" else native_staff_client(
        space, platform, settings, monkeypatch)[0]
    space.resource_limit_overrides = {"shop_products": 1}
    space.save(update_fields=["resource_limit_overrides"])
    url = f"/api/v1/admin/makerspaces/{space.pk}/shop/products/"
    body = {"name": "Last product", "kind": "other", "price": "1.00"}
    maximum = caller.post(url, body, format="json")
    assert maximum.status_code == 201
    refused = caller.post(url, {**body, "name": "Excess product"}, format="json")
    assert refused.status_code == 409
    assert refused.json()["code"] == "shop_products_quota_reached"
    listing = caller.get(url)
    assert listing.status_code == 200
    assert listing.json()["count"] == 1


@pytest.mark.parametrize("surface", ["online", "desk", "apple", "android"])
@pytest.mark.parametrize("key", ["shop_orders_monthly", "payments_monthly_count", "payments_monthly_amount"])
def test_order_and_money_capacity_last_slot_and_next_exact_refusal(surface, key, settings, monkeypatch):
    from .helpers import client, member, shop_manager
    space = shop_space("cx7-order-capacity", "shop.online", "shop.holds")
    if surface in ("apple", "android"):
        caller, actor = native_staff_client(space, surface, settings, monkeypatch)
    else:
        actor = shop_manager(space)
        caller = client(member(space)) if surface == "online" else client(actor)
    _, variant = product(space, actor, price="1.00", stock=3)
    space.resource_limit_overrides = {key: 1}
    space.save(update_fields=["resource_limit_overrides"])
    url = f"/api/v1/public/m/{space.slug}/shop/orders/" if surface == "online" else (
        f"/api/v1/admin/makerspaces/{space.pk}/shop/pos/sale/")
    body = {"lines": [line(variant)], "method": "upi"}
    maximum = caller.post(url, body, format="json")
    assert maximum.status_code == 201
    order = ShopOrder.objects.get(makerspace=space)
    payment = Payment.objects.get(makerspace=space)
    assert (order.total, payment.amount) == (Decimal("1.00"), Decimal("1.00"))
    variant.refresh_from_db()
    before = (variant.on_hand, variant.held, variant.movements.count())
    refused = caller.post(url, body, format="json")
    assert refused.status_code == 409
    assert refused.json()["code"] == ("shop_orders_monthly_quota_reached" if key == "shop_orders_monthly" else "payment_quota_reached")
    assert str(refused.json()["limit"]) == "1"
    assert ShopOrder.objects.filter(makerspace=space).count() == 1
    assert Payment.objects.filter(makerspace=space).count() == 1
    variant.refresh_from_db()
    assert (variant.on_hand, variant.held, variant.movements.count()) == before


@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
@pytest.mark.parametrize("disabled", ["charges.enabled", "charges.shop"])
def test_charges_off_keeps_catalogue_creation_and_stock_management(surface, disabled, settings, monkeypatch):
    from .helpers import client, shop_manager
    space = shop_space("cx7-catalogue-management")
    caller = client(shop_manager(space)) if surface == "browser" else native_staff_client(
        space, surface, settings, monkeypatch)[0]
    switch(space, disabled, on=False)
    created = caller.post(f"/api/v1/admin/makerspaces/{space.pk}/shop/products/",
        {"name": "Managed while sales are off", "kind": "other", "price": "2.50"}, format="json")
    assert created.status_code == 201
    variant = created.json()["variants"][0]
    assert variant["price"] == "2.50"
    restocked = caller.post(f"/api/v1/admin/shop/variants/{variant['id']}/stock/",
        {"kind": "restock", "quantity": 3, "reason": "Restock without selling"}, format="json")
    assert restocked.status_code == 200
    assert (restocked.json()["on_hand"], restocked.json()["held"]) == (3, 0)
    assert restocked.json()["price"] == "2.50"
    assert Payment.objects.filter(makerspace=space).count() == 0
    assert ShopOrder.objects.filter(makerspace=space).count() == 0
