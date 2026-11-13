"""L22 on/off (#95): every shop route answers 404 with the module off, features gate their routes,
the sweep touches nothing in a switched-off space, and data survives the round trip."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.shop.models import ShopOrder

from .helpers import client, line, manager, member, module_off, product, shop_manager, shop_space, switch

pytestmark = pytest.mark.django_db

STAFF_GETS = ("orders/", "products/", "movements/", "settings/", "report/", "cash-sessions/")


def test_every_route_is_404_with_the_module_off_and_back_with_it_on():
    space = shop_space("onoff-a", "shop.online", "shop.cash_up")
    sm = manager(space)
    _row, variant = product(space, sm)
    module_off(space)
    for path in STAFF_GETS:
        response = client(sm).get(f"/api/v1/admin/makerspaces/{space.pk}/shop/{path}")
        assert response.status_code == 404, path
    assert client(sm).post(f"/api/v1/admin/makerspaces/{space.pk}/shop/pos/sale/",
                           {"lines": [line(variant)], "method": "cash"}, format="json").status_code == 404
    for tail in ("", "products/", f"products/{variant.product.slug}/"):
        assert client().get(f"/api/v1/public/m/{space.slug}/shop/{tail}").status_code == 404, tail
    assert client(member(space)).get("/api/v1/member/shop/orders/").json()["count"] == 0
    switch(space, modules=("shop",))
    assert client(sm).get(f"/api/v1/admin/makerspaces/{space.pk}/shop/products/").json()["count"] == 1


def test_the_online_page_needs_its_switch_and_the_public_site():
    space = shop_space("onoff-b")
    assert client().get(f"/api/v1/public/m/{space.slug}/shop/").json()["code"] == "feature_off"
    switch(space, "shop.online")
    assert client().get(f"/api/v1/public/m/{space.slug}/shop/").status_code == 200
    from apps.makerspaces.models import Makerspace
    Makerspace.objects.filter(pk=space.pk).update(public_site_enabled=False)
    assert client().get(f"/api/v1/public/m/{space.slug}/shop/").status_code == 404


def test_cash_up_routes_need_their_switch():
    space = shop_space("onoff-c")
    seller = shop_manager(space)
    response = client(seller).get(f"/api/v1/admin/makerspaces/{space.pk}/shop/cash-sessions/")
    assert response.status_code == 404 and response.json()["code"] == "feature_off"


def test_the_sweep_runs_nothing_for_a_switched_off_space():
    from apps.shop.tasks import sweep_shop_task

    space = shop_space("onoff-d", "shop.online", "shop.holds")
    _row, variant = product(space, manager(space), stock=2)
    order_id = client(member(space)).post(f"/api/v1/public/m/{space.slug}/shop/orders/", {"lines": [line(variant)]},
                                          format="json").json()["order"]["id"]
    ShopOrder.objects.filter(pk=order_id).update(expires_at=timezone.now() - timedelta(minutes=5))
    module_off(space)
    sweep_shop_task()
    assert ShopOrder.objects.get(pk=order_id).status == "awaiting_payment"
    switch(space, modules=("shop",))
    sweep_shop_task()
    assert ShopOrder.objects.get(pk=order_id).status == "cancelled"


def test_the_bootstrap_lists_the_module_and_its_features_only_when_on():
    from apps.makerspaces.platform import bootstrap_payload

    space = shop_space("onoff-e", "shop.online")
    payload = bootstrap_payload(space)
    assert "shop" in payload["modules"] and "shop.online" in payload["features"]
    module_off(space)
    payload = bootstrap_payload(space)
    assert "shop" not in payload["modules"] and "shop.online" not in payload["features"]


def test_the_pages_section_shows_items_only_when_the_online_shop_is_on():
    from apps.shop.public import page_cards

    space = shop_space("onoff-f")
    product(space, manager(space), name="Card item")
    assert page_cards(space) == []
    switch(space, "shop.online")
    assert [card["name"] for card in page_cards(space)] == ["Card item"]


@pytest.mark.parametrize("key", ["charges.shop", "charges.enabled"])
def test_untracked_shop_browses_without_prices_and_cannot_quote(key):
    from apps.shop.public import page_cards

    space = shop_space("onoff-prices", "shop.online")
    seller = shop_manager(space)
    row, variant = product(space, seller)
    base = f"/api/v1/public/m/{space.slug}/shop/"
    staff_base = f"/api/v1/admin/makerspaces/{space.pk}/shop/"
    body = {"lines": [line(variant)]}
    assert client().post(f"{base}quote/", body, format="json").status_code == 200

    switch(space, key, on=False)
    listing = client().get(f"{base}products/")
    detail = client().get(f"{base}products/{row.slug}/")
    assert listing.status_code == detail.status_code == 200
    for public_row in (listing.json()["results"][0], detail.json()):
        assert public_row["name"] == row.name
        assert public_row["price_from"] is public_row["price_to"] is None
        assert public_row["variants"][0]["price"] is None
    assert page_cards(space)[0]["price_from"] is None

    for response in (client().post(f"{base}quote/", body, format="json"),
                     client(seller).post(f"{staff_base}pos/quote/", body, format="json")):
        assert response.status_code == 404 and response.json()["code"] == "charges_off"

    staff_product = client(seller).get(f"{staff_base}products/").json()["results"][0]
    assert staff_product["variants"][0]["price"] == "100.00"
    switch(space, key)
    listing = client().get(f"{base}products/").json()["results"][0]
    detail = client().get(f"{base}products/{row.slug}/").json()
    for public_row in (listing, detail):
        assert public_row["price_from"] == public_row["price_to"] == public_row["variants"][0]["price"] == 100.0
