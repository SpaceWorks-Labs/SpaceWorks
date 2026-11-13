"""Event interruption changes pickup instructions, while the Shop order survives."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.events.services_lifecycle import cancel
from apps.hardware_requests.contact_verification import issue_code
from apps.makerspaces.models import Makerspace
from apps.payments.models_refund_cases import RefundCase
from apps.shop.models import ShopOrder
from apps.shop.notices import _copy, status_token
from apps.shop.serializers_public import ShopBuyerOrderSerializer
from apps.shop.views_member import my_orders
from tests.events.ticketing_helpers import open_event

from .helpers import client, line, manager, member, payment_for, product, shop_manager, shop_space, switch

pytestmark = pytest.mark.django_db


def test_event_cancellation_requires_confirmation_without_releasing_shop_obligations(django_assert_num_queries):
    space = shop_space("event-shop-handoff", "shop.online", "shop.holds", "shop.event_pickup")
    switch(space, modules=("events",))
    actor = manager(space)
    buyer = member(space)
    seller = shop_manager(space)
    event = open_event(space)
    _product, variant = product(space, actor, price="40.00", stock=3)
    base = f"/api/v1/public/m/{space.slug}/shop/orders/"
    placed = client(buyer).post(base, {
        "lines": [line(variant)], "pickup_at": "event", "pickup_event_id": event.pk,
    }, format="json")
    assert placed.status_code == 201, placed.content
    assert placed.json()["order"]["pickup_requires_staff_confirmation"] is False
    order = ShopOrder.objects.get(pk=placed.json()["order"]["id"])
    payment = payment_for(order)
    holds = list(order.holds.values())
    variant.refresh_from_db()
    stock = (variant.on_hand, variant.held)
    member_url = f"/api/v1/member/shop/orders/{order.pk}/"
    staff_url = f"/api/v1/admin/shop/orders/{order.pk}/"
    signed_url = f"{base}{status_token(order)}/"

    cancel(event, actor=actor, notify=False)
    order.refresh_from_db()
    subject, reminder = _copy(order, "shop_order_reminder")
    assert "confirm where to collect" in reminder
    assert order.pickup_code not in subject and order.pickup_code not in reminder

    for response in (client(buyer).get(member_url), client().get(signed_url), client(seller).get(staff_url)):
        assert response.status_code == 200, response.content
        payload = response.json()
        assert payload["pickup_requires_staff_confirmation"] is True
        assert payload["pickup_event_title"] == event.title
        assert payload["status"] == "awaiting_payment"
        assert payload["pickup_code"] == order.pickup_code
        assert payload["paid_at"] is None and payload["ready_at"] is None
    assert client(member(space, "unrelated")).get(member_url).status_code == 404
    assert client().get(f"{base}forged/").status_code == 404
    rows = list(my_orders(buyer))
    with django_assert_num_queries(0):
        assert ShopBuyerOrderSerializer(rows, many=True).data[0]["pickup_requires_staff_confirmation"] is True
    variant.refresh_from_db()
    assert (variant.on_hand, variant.held) == stock
    assert list(order.holds.values()) == holds
    current_payment = payment_for(order)
    assert (current_payment.pk, current_payment.status, current_payment.amount) == (payment.pk, payment.status, payment.amount)
    assert not RefundCase.objects.filter(payment=payment).exists()
    assert ShopOrder.objects.filter(makerspace=space).count() == 1


def test_existing_event_pickup_needs_confirmation_only_while_active_and_unavailable():
    space = shop_space("event-shop-off", "shop.online", "shop.event_pickup")
    space.enabled_modules = [module for module in space.enabled_modules if module != "events"]
    event = open_event(space)
    order = ShopOrder(makerspace=space, pickup_at="event", pickup_event=event, status="ready")
    from apps.shop.pickup_status import pickup_event_title, pickup_requires_staff_confirmation

    assert pickup_requires_staff_confirmation(order)
    switch(space, modules=("events",))
    assert not pickup_requires_staff_confirmation(order)
    event.is_public = False
    assert not pickup_requires_staff_confirmation(order)
    event.ends_at = timezone.now() - timedelta(minutes=1)
    assert pickup_requires_staff_confirmation(order)
    order.status = "collected"
    assert not pickup_requires_staff_confirmation(order)
    order.status = "ready"
    order.pickup_event = None
    assert pickup_requires_staff_confirmation(order)
    order.pickup_event = open_event(shop_space("event-shop-foreign"))
    assert pickup_requires_staff_confirmation(order)
    assert pickup_event_title(order) == ""
    order.pickup_at = "space"
    assert not pickup_requires_staff_confirmation(order)


def test_guest_order_keeps_its_signed_handoff_when_events_is_disabled(monkeypatch):
    space = shop_space("guest-event-pickup", "shop.online", "shop.event_pickup", "shop.guest_checkout")
    switch(space, modules=("events",))
    actor = manager(space)
    event = open_event(space)
    _product, variant = product(space, actor)
    address = "event-guest@example.test"
    monkeypatch.setattr("apps.hardware_requests.contact_verification._generate_otp", lambda: "123456")
    monkeypatch.setattr("apps.integrations.email.send_email_verification_otp", lambda *_: True)
    issue_code(space, address)

    base = f"/api/v1/public/m/{space.slug}/shop/orders/"
    placed = client().post(base, {
        "lines": [line(variant)], "pickup_at": "event", "pickup_event_id": event.pk,
        "guest_name": "Event guest", "guest_email": address, "email_code": "123456",
    }, format="json")
    assert placed.status_code == 201, placed.content
    data = placed.json()
    order = ShopOrder.objects.get(pk=data["order"]["id"])
    assert order.buyer_id is None and payment_for(order).member_id is None
    assert data["order"]["pickup_requires_staff_confirmation"] is False

    Makerspace.objects.filter(pk=space.pk).update(
        enabled_modules=sorted(set(space.enabled_modules) - {"events"}),
    )
    token = data["status_token"]
    status = client().get(f"{base}{token}/")
    assert status.status_code == 200, status.content
    assert status.json()["pickup_requires_staff_confirmation"] is True
    assert status.json()["pickup_event_title"] == event.title
    assert status.json()["status"] == data["order"]["status"]
    other = shop_space("guest-other-pickup", "shop.online")
    assert client().get(f"/api/v1/public/m/{other.slug}/shop/orders/{token}/").status_code == 404
