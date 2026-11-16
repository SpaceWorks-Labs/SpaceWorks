"""Own-order fulfilment facts survive switch-off; returns never imply money was sent."""

import pytest

from apps.payments.models import Refund
from apps.shop.models import ShopOrder, ShopOrderReturn
from apps.shop.notices import status_token

from .helpers import client, line, member, payment_for, product, shop_manager, shop_space, switch

pytestmark = pytest.mark.django_db


def returned_order(space, buyer=None):
    seller = shop_manager(space)
    _product, variant = product(space, seller, price="40.00", stock=3)
    body = {"lines": [line(variant, 2)], "method": "cash"}
    if buyer:
        body["member_id"] = buyer.pk
    sale = client(seller).post(f"/api/v1/admin/makerspaces/{space.pk}/shop/pos/sale/", body, format="json")
    assert sale.status_code == 201, sale.content
    order = ShopOrder.objects.get(pk=sale.json()["id"])
    returned = client(seller).post(f"/api/v1/admin/shop/orders/{order.pk}/returns/", {
        "rows": [{"line_id": order.lines.get().pk, "quantity": 2, "disposition": "write_off"}],
        "reason": "Staff-only inspection note",
    }, format="json")
    assert returned.status_code == 200, returned.content
    order.refresh_from_db()
    return order


def assert_safe_history(payload, order):
    assert payload["closed_at"] and payload["paid_at"] and payload["collected_at"]
    assert payload["status"] == "refunded"  # Compatibility enum means goods returned, not cash paid back.
    assert payload["returns"] == [{"line_id": order.lines.get().pk, "quantity": 2, "amount": "80.00",
                                   "created_at": payload["returns"][0]["created_at"]}]
    assert payload["returns"][0]["created_at"]
    assert not {"reason", "disposition", "refund_case_id", "created_by"} & payload["returns"][0].keys()
    assert "Staff-only inspection note" not in str(payload)
    assert not Refund.objects.filter(payment=payment_for(order)).exists()


def test_owner_history_retains_returns_with_returns_and_online_rail_off():
    space = shop_space("buyer-history", "shop.returns")
    buyer = member(space)
    order = returned_order(space, buyer)
    switch(space, "shop.returns", "shop.online", "payments.enabled", "payments.shop", on=False)
    detail = client(buyer).get(f"/api/v1/member/shop/orders/{order.pk}/")
    assert detail.status_code == 200, detail.content
    assert_safe_history(detail.json(), order)
    listing = client(buyer).get(f"/api/v1/member/shop/orders/?makerspace_id={space.pk}")
    assert listing.status_code == 200
    assert_safe_history(listing.json()["results"][0], order)


def test_foreign_account_and_foreign_tenant_cannot_read_another_buyer_history():
    space = shop_space("buyer-private", "shop.returns")
    buyer = member(space)
    order = returned_order(space, buyer)
    outsider = member(space, "outsider")
    foreign = member(shop_space("buyer-other"))
    for person in (outsider, foreign):
        assert client(person).get(f"/api/v1/member/shop/orders/{order.pk}/").status_code == 404
        response = client(person).get(f"/api/v1/member/shop/orders/?makerspace_id={space.pk}")
        assert response.status_code == 200 and response.json()["results"] == []


def test_guest_history_requires_exact_signed_order_token_and_tenant():
    space = shop_space("guest-history", "shop.returns", "shop.online")
    order = returned_order(space)
    switch(space, "shop.returns", on=False)
    token = status_token(order)
    path = f"/api/v1/public/m/{space.slug}/shop/orders/{token}/"
    response = client().get(path)
    assert response.status_code == 200, response.content
    assert_safe_history(response.json(), order)
    other = shop_space("guest-foreign", "shop.online")
    assert client().get(path.replace(f"/m/{space.slug}/", f"/m/{other.slug}/")).status_code == 404
    assert client().get(path.replace(token, "forged")).status_code == 404
    assert client().get(f"/api/v1/member/shop/orders/{order.pk}/").status_code in (401, 403)


@pytest.mark.parametrize("guest", [False, True])
def test_inconsistent_tenant_or_line_children_never_enter_buyer_history(guest):
    space = shop_space(f"history-child-{guest}", "shop.returns", "shop.online")
    buyer = None if guest else member(space)
    order = returned_order(space, buyer)
    foreign = shop_space(f"history-child-other-{guest}")
    own_line = order.lines.get()
    bad_tenant = ShopOrderReturn.objects.create(makerspace=foreign, order=order, line=own_line,
                                                quantity=1, amount="99.00", disposition="restock")
    other_order = ShopOrder.objects.create(makerspace=space, currency="INR", pickup_code="OTHER42")
    from apps.shop.models import ShopOrderLine
    other_line = ShopOrderLine.objects.create(order=other_order, variant=own_line.variant, label="Private other order",
                                              quantity=1, unit_amount="7.00", line_total="7.00")
    bad_line = ShopOrderReturn.objects.create(makerspace=space, order=order, line=other_line,
                                              quantity=1, amount="7.00", disposition="restock")
    if guest:
        response = client().get(f"/api/v1/public/m/{space.slug}/shop/orders/{status_token(order)}/")
        payloads = [response.json()]
    else:
        response = client(buyer).get(f"/api/v1/member/shop/orders/{order.pk}/")
        listing = client(buyer).get(f"/api/v1/member/shop/orders/?makerspace_id={space.pk}")
        assert listing.status_code == 200
        payloads = listing.json()["results"] + [response.json()]
    assert response.status_code == 200, response.content
    for payload in payloads:
        assert_safe_history(payload, order)
        assert "Private other order" not in str(payload)
    assert ShopOrderReturn.objects.filter(pk__in=[bad_tenant.pk, bad_line.pk]).count() == 2


def test_member_history_serializer_consumes_prefetched_children_without_per_order_queries(django_assert_num_queries):
    from apps.shop.serializers_public import ShopBuyerOrderSerializer
    from apps.shop.views_member import my_orders

    space = shop_space("history-prefetch", "shop.returns")
    buyer = member(space)
    order = returned_order(space, buyer)
    rows = list(my_orders(buyer))
    assert [row.pk for row in rows] == [order.pk]
    with django_assert_num_queries(0):
        payload = ShopBuyerOrderSerializer(rows, many=True).data
    assert len(payload[0]["returns"]) == 1
