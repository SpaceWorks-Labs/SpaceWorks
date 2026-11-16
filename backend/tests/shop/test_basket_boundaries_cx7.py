"""Fixed basket limits keep the decided field-validation response bodies."""
from decimal import Decimal

import pytest

from .helpers import client, line, product, shop_manager, shop_space

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("surface", ["public", "staff"])
def test_raw_basket_accepts_50_lines_and_refuses_51_with_exact_field_body(surface):
    space = shop_space("cx7-basket-lines", "shop.online")
    seller = shop_manager(space)
    _, variant = product(space, seller, stock=100)
    caller, url = (client(), f"/api/v1/public/m/{space.slug}/shop/quote/") if surface == "public" else (
        client(seller), f"/api/v1/admin/makerspaces/{space.pk}/shop/pos/quote/")
    maximum = caller.post(url, {"lines": [line(variant)] * 50}, format="json")
    assert maximum.status_code == 200
    assert Decimal(maximum.json()["lines"][0]["quantity"]) == 50
    refused = caller.post(url, {"lines": [line(variant)] * 51}, format="json")
    assert refused.status_code == 400
    assert refused.json() == {"lines": {"non_field_errors": ["Ensure this field has no more than 50 elements."]}}


def test_internal_basket_accepts_50_distinct_variants_and_refuses_51():
    from apps.shop.errors import ShopRefused
    from apps.shop.pricing import _merged
    maximum = [{"variant_id": index, "quantity": 1} for index in range(1, 51)]
    assert dict(_merged(maximum)) == {index: 1 for index in range(1, 51)}
    with pytest.raises(ShopRefused) as raised:
        _merged([*maximum, {"variant_id": 51, "quantity": 1}])
    assert raised.value.status_code == 400
    assert raised.value.code == "variant_invalid"
    assert raised.value.detail == {"code": "variant_invalid", "detail": "An order holds at most 50 different items."}
