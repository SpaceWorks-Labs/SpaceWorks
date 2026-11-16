"""Catalogue/settings/image routes: exact persisted effects, standing and retention."""
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.shop.models import ShopProduct, ShopSettings, ShopStockMovement, ShopVariant
from tests.payments.route_support_cx11b_g5 import cycle, hidden, ids, world
from tests.shop.route_fixtures_cx11b_g5 import seed

pytestmark = [pytest.mark.django_db, pytest.mark.area_shop]
OPERATIONS = (
    ("admin-shop-settings", "GET"), ("admin-shop-settings", "PATCH"),
    ("admin-shop-products", "GET"), ("admin-shop-products", "POST"),
    ("admin-shop-product", "GET"), ("admin-shop-product", "PATCH"), ("admin-shop-product", "DELETE"),
    ("admin-shop-product-image", "POST"), ("admin-shop-product-image", "PUT"),
    ("admin-shop-product-image", "DELETE"), ("admin-shop-variant", "DELETE"),
    ("admin-shop-variant-stock", "POST"), ("admin-shop-movements", "GET"),
)


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("name,method", OPERATIONS)
def test_catalogue_route_effect_off_fence_standing_and_restore(native, name, method, monkeypatch, settings):
    s = seed(native)
    kwargs = {"makerspace_id": s.space.pk} if name in {
        "admin-shop-settings", "admin-shop-products", "admin-shop-movements"} else {
        "pk": s.variant.pk if "variant" in name else s.product.pk}
    body, audit, on = {}, (), (200, None)
    if name == "admin-shop-settings" and method == "PATCH":
        body, audit = {"desk_hold_hours": 36}, ("settings.changed",)
    elif name == "admin-shop-products" and method == "POST":
        body, audit, on = {"name": "G5 new product", "price": "7.25"}, (
            "shop.variant_created", "shop.product_created"), (201, None)
    elif name == "admin-shop-product" and method == "PATCH":
        body, audit = {"description": "G5 saved description"}, ("shop.product_updated",)
    elif method == "DELETE":
        audit = ({"admin-shop-product": "shop.product_archived", "admin-shop-variant": "shop.variant_archived",
                  "admin-shop-product-image": "shop.product_image_cleared"}[name],)
    elif name == "admin-shop-variant-stock":
        body, audit = {"kind": "restock", "quantity": 3, "reason": "G5 delivery"}, ("shop.stock_restocked",)
    key = f"shop/{s.space.pk}/g5.png"
    storage_calls = []
    if name == "admin-shop-product-image":
        from apps.inventory import public_image_storage as storage
        settings.PUBLIC_IMAGE_BASE_URL = "https://cdn.example.test"
        def presign(object_key, content_type):
            storage_calls.append((object_key, content_type))
            return {"url": "https://storage.example.test/stage", "fields": {"key": storage.staging_key(object_key)}}
        monkeypatch.setattr(storage, "presigned_upload", presign)
        monkeypatch.setattr(storage, "finalize_upload", lambda value: storage._finalize_result(value, 123))
        monkeypatch.setattr(storage, "sniff_is_valid_image", lambda value: True)
        if method == "POST":
            body, on = {"filename": "g5.png", "content_type": "image/png"}, (201, None)
        elif method == "PUT":
            body, audit = {"object_key": key}, ("shop.product_image_set",)
        else:
            ShopProduct.objects.filter(pk=s.product.pk).update(image_key=key)

    def result(response):
        row = ShopProduct.objects.get(pk=s.product.pk)
        variant = ShopVariant.objects.get(pk=s.variant.pk)
        if name == "admin-shop-settings":
            assert response.data["policy_text"] == "G5 retained policy"
            expected = 36 if method == "PATCH" else 48
            assert ShopSettings.objects.get(makerspace=s.space).desk_hold_hours == expected
            assert response.data["desk_hold_hours"] == expected
        elif name == "admin-shop-products" and method == "GET":
            assert ids(response) == [row.pk]
            assert response.data["results"][0]["variants"][0]["id"] == variant.pk
        elif name == "admin-shop-products":
            made = ShopProduct.objects.get(pk=response.data["id"])
            assert (made.name, made.makerspace_id) == ("G5 new product", s.space.pk)
            assert list(made.variants.values_list("price", flat=True)) == [Decimal("7.25")]
            assert ShopProduct.objects.filter(makerspace=s.space).count() == 2
        elif name == "admin-shop-product-image":
            if method == "POST":
                assert response.data["object_key"].startswith(f"shop/{s.space.pk}/")
                assert storage_calls[-1] == (response.data["object_key"], "image/png")
                assert response.data["fields"]["key"] != response.data["object_key"]
                assert row.image_key == ""
            else:
                assert row.image_key == (key if method == "PUT" else "")
                assert response.data["image_url"] == (f"https://cdn.example.test/{key}" if method == "PUT" else "")
        elif name == "admin-shop-product":
            assert response.data["id"] == row.pk
            if method == "PATCH":
                assert row.description == response.data["description"] == "G5 saved description"
            elif method == "DELETE":
                assert row.archived_at is not None and variant.archived_at is not None
            else:
                assert response.data["name"] == "Widget"
        elif name == "admin-shop-variant":
            assert variant.archived_at is not None and row.archived_at is None
        elif name == "admin-shop-variant-stock":
            assert variant.on_hand == response.data["on_hand"] == 11
            assert list(ShopStockMovement.objects.filter(variant=variant).order_by("pk").values_list(
                "kind", "quantity", "balance_after", "reason")) == [
                    ("restock", 8, 8, "seed"), ("restock", 3, 11, "G5 delivery")]
        else:
            assert response.data["count"] == 1
            assert [(r["variant"], r["quantity"], r["balance_after"]) for r in response.data["results"]] == [(variant.pk, 8, 8)]

    # Decisions 481/494/520: scoped staff without standing get 404 in all switch states.
    w = world(s.space, s.client, reverse(name, kwargs=kwargs), method, body, on, audit, result,
              probes=[hidden(s.foreign)])
    cycle(w, "shop", (404, "shop_closed"))
