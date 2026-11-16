"""Two different products/baskets must not both fit a single remaining slot."""
import pytest
from django.db import connection
from rest_framework.test import APIClient

from apps.shop.models import ShopOrder, ShopProduct
from tests.limits_0120.concurrency_helpers_cx7 import race_posts
from tests.shop.helpers import client, line, product, shop_manager, shop_space
from tests.shop.test_native_shop_limits_cx7 import native_staff_client

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
@pytest.mark.parametrize("key", ["shop_products", "shop_orders_monthly"])
def test_two_shop_http_creates_at_last_slot_have_one_exact_refusal(key, surface, settings, monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    settings.MANAGED_PLANS_ENABLED = False
    space = shop_space("cx7-shop-api-race")
    if surface == "browser":
        actor = shop_manager(space)
        pair = [client(actor), client(actor)]
    else:
        first, actor = native_staff_client(space, surface, settings, monkeypatch)
        second = APIClient()
        second.credentials(**first._credentials)
        pair = [first, second]
    base = f"/api/v1/admin/makerspaces/{space.pk}/shop/"
    if key == "shop_products":
        url = base + "products/"
        bodies = [{"name": name, "kind": "merch", "price": "1.00"} for name in ("A", "B")]
    else:
        # Distinct variants ensure a stock-row lock cannot conceal a missing
        # space-level quota lock.
        variants = [product(space, actor, name=name, stock=2)[1] for name in ("A", "B")]
        url = base + "pos/sale/"
        bodies = [{"lines": [line(variant)], "method": "upi"} for variant in variants]
    space.resource_limit_overrides = {key: 1}
    space.save(update_fields=["resource_limit_overrides"])
    results = race_posts(pair, url, bodies)
    assert sorted(status for status, _ in results) == [201, 409]
    assert [body["code"] for status, body in results if status == 409] == [f"{key}_quota_reached"]
    if key == "shop_products":
        assert ShopProduct.objects.filter(makerspace=space).count() == 1
    else:
        assert ShopOrder.objects.filter(makerspace=space).count() == 1
