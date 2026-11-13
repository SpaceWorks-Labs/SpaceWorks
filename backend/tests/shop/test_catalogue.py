"""L22 catalogue: products, variants, archive, members-only, links, bundles (local, untracked)."""

from decimal import Decimal

import pytest

from apps.shop.errors import ShopRefused
from apps.shop.models import ShopProduct, ShopVariant
from apps.shop.services_catalogue import archive_product, save_product

from .helpers import client, manager, member, product, shop_space, switch

pytestmark = pytest.mark.django_db


def test_a_product_without_options_gets_one_default_variant_and_a_unique_slug():
    space = shop_space("cat-a")
    sm = manager(space)
    first = save_product(space, {"name": "Solder", "price": Decimal("50")}, actor=sm)
    second = save_product(space, {"name": "Solder", "price": Decimal("60")}, actor=sm)
    assert first.variants.count() == 1 and first.variants.get().price == Decimal("50")
    assert first.slug == "solder" and second.slug == "solder-2"


def test_variants_carry_their_own_price_and_sku_is_unique_per_space():
    space = shop_space("cat-b")
    sm = manager(space)
    shirt = save_product(space, {"kind": "merch", "name": "Tee", "variants": [
        {"name": "S", "options": {"size": "S"}, "sku": "TEE-S", "price": Decimal("10")},
        {"name": "M", "options": {"size": "M"}, "sku": "TEE-M", "price": Decimal("12")}]}, actor=sm)
    assert sorted(shirt.variants.values_list("price", flat=True)) == [Decimal("10"), Decimal("12")]
    with pytest.raises(ShopRefused) as caught:
        save_product(space, {"name": "Other", "variants": [{"name": "x", "sku": "TEE-S", "price": 1}]}, actor=sm)
    assert caught.value.code == "variant_invalid"


def test_options_are_short_pairs_only():
    space = shop_space("cat-c")
    with pytest.raises(ShopRefused):
        save_product(space, {"name": "Bad", "variants": [{"name": "x", "price": 1,
                                                          "options": {"a": "1", "b": "2", "c": "3", "d": "4"}}]},
                     actor=manager(space))


def test_archive_hides_the_product_from_the_public_page_but_keeps_it():
    space = shop_space("cat-d", "shop.online")
    sm = manager(space)
    row, _variant = product(space, sm, name="Gone")
    archive_product(row, actor=sm)
    assert ShopProduct.objects.filter(pk=row.pk, archived_at__isnull=False).exists()
    assert ShopVariant.objects.filter(product=row, is_active=False).count() == 1
    response = client().get(f"/api/v1/public/m/{space.slug}/shop/products/")
    assert response.status_code == 200 and response.json()["count"] == 0


def test_members_only_needs_member_prices_and_a_member_of_this_space():
    space = shop_space("cat-e", "shop.online", "shop.member_prices", "charges.discounts")
    sm = manager(space)
    _row, variant = product(space, sm, name="Members tee", members_only=True)
    anon = client().post(f"/api/v1/public/m/{space.slug}/shop/quote/", {"lines": [{"variant_id": variant.pk,
                                                                                   "quantity": 1}]}, format="json")
    assert anon.status_code == 403 and anon.json()["code"] == "member_only"
    ok = client(member(space)).post(f"/api/v1/public/m/{space.slug}/shop/quote/",
                                    {"lines": [{"variant_id": variant.pk, "quantity": 1}]}, format="json")
    assert ok.status_code == 200


def test_linking_a_consumable_needs_the_switch_and_never_a_lendable_tool():
    from apps.inventory.models import InventoryProduct

    space = shop_space("cat-f")
    sm = manager(space)
    tool = InventoryProduct.objects.create(makerspace=space, name="Drill", is_consumable=False)
    with pytest.raises(ShopRefused):
        save_product(space, {"name": "x", "variants": [{"name": "s", "price": 1, "linked_product_id": tool.pk}]},
                     actor=sm)
    switch(space, "shop.consumable_link")
    with pytest.raises(ShopRefused) as caught:
        save_product(space, {"name": "y", "variants": [{"name": "s", "price": 1, "linked_product_id": tool.pk}]},
                     actor=sm)
    assert caught.value.code == "link_invalid"


def test_bundle_parts_need_the_switch_and_a_kit():
    space = shop_space("cat-g")
    sm = manager(space)
    _part, variant = product(space, sm, name="Board")
    with pytest.raises(ShopRefused):
        save_product(space, {"kind": "kit", "name": "Kit", "bundle_mode": True, "price": 5,
                             "components": [{"variant_id": variant.pk, "quantity": 2}]}, actor=sm)
    switch(space, "shop.bundles")
    kit = save_product(space, {"kind": "kit", "name": "Kit", "bundle_mode": True, "price": 5,
                               "components": [{"variant_id": variant.pk, "quantity": 2}]}, actor=sm)
    assert kit.components.get().quantity == 2
    with pytest.raises(ShopRefused):
        save_product(space, {"kind": "merch", "name": "Not a kit", "bundle_mode": True, "price": 5}, actor=sm)


def test_staff_api_creates_and_archives_and_audits():
    from apps.audit.models import AuditLog

    space = shop_space("cat-h")
    sm = manager(space)
    created = client(sm).post(f"/api/v1/admin/makerspaces/{space.pk}/shop/products/",
                              {"name": "Glue", "kind": "consumable", "price": "40.00"}, format="json")
    assert created.status_code == 201, created.content
    pk = created.json()["id"]
    assert client(sm).delete(f"/api/v1/admin/shop/products/{pk}/").status_code == 200
    actions = set(AuditLog.objects.filter(makerspace=space).values_list("action", flat=True))
    assert {"shop.product_created", "shop.variant_created", "shop.product_archived"} <= actions
