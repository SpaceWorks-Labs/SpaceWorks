"""The desk may persist one alternate pickup without altering order obligations."""
import pytest

from apps.audit.models import AuditLog
from apps.events.services_lifecycle import cancel
from apps.makerspaces.models import Makerspace
from apps.payments.models_refund_cases import RefundCase
from apps.shop import notices
from apps.shop.models import ShopOrder
from apps.shop.services_pos import collect_payment
from tests.events.ticketing_helpers import open_event

from .helpers import client, line, manager, member, payment_for, product, shop_manager, shop_space, staff, switch

pytestmark = pytest.mark.django_db
ACTION = "shop.order_pickup_moved_to_space"


def _event_order(slug):
    space = shop_space(slug, "shop.online", "shop.holds", "shop.event_pickup")
    switch(space, modules=("events",))
    actor, buyer = manager(space), member(space)
    event = open_event(space)
    _product, variant = product(space, actor, price="40.00", stock=3)
    placed = client(buyer).post(f"/api/v1/public/m/{space.slug}/shop/orders/", {
        "lines": [line(variant)], "pickup_at": "event", "pickup_event_id": event.pk,
    }, format="json")
    assert placed.status_code == 201, placed.content
    order = ShopOrder.objects.get(pk=placed.json()["order"]["id"])
    return space, actor, buyer, event, variant, order, f"/api/v1/admin/shop/orders/{order.pk}/move-pickup-to-space/"


def _observe(monkeypatch):
    attempts = []
    original = notices.buyer_notice

    def observe(order, event, marker=None):
        if event == "shop_order_pickup_moved_to_space":
            attempts.append((event, marker, notices._copy(order, event)))
        return original(order, event, marker=marker)

    monkeypatch.setattr(notices, "buyer_notice", observe)
    return attempts


def _records(space, order):
    return AuditLog.objects.filter(makerspace=space, target_type="shop.shoporder", target_id=str(order.pk),
                                   action=ACTION)


def test_interrupted_event_pickup_moves_once_through_the_authorized_desk(monkeypatch):
    space, actor, buyer, event, variant, order, path = _event_order("move-event-pickup")
    seller = shop_manager(space)
    variant.refresh_from_db()
    stock = (variant.on_hand, variant.held)
    holds = list(order.holds.order_by("pk").values())
    payment = payment_for(order)
    assert client(seller).post(path).status_code == 409  # the event is still on: nothing to move
    cancel(event, actor=actor, notify=False)
    assert client(shop_manager(shop_space("move-event-foreign"))).post(path).status_code == 404
    assert client(staff(space, "inventory_manager")).post(path).status_code == 404
    assert client(buyer).post(path).status_code in (403, 404)
    assert not _records(space, order).exists()
    attempts = _observe(monkeypatch)
    for _ in range(2):
        response = client(seller).post(path)
        assert response.status_code == 200, response.content
        assert response.json()["pickup_at"] == "space"
        assert response.json()["pickup_event"] is None
        assert response.json()["pickup_requires_staff_confirmation"] is False
    assert len(attempts) == 1
    notice, marker, (subject, message) = attempts[0]
    assert (notice, marker) == ("shop_order_pickup_moved_to_space", "space")
    assert space.name in message and order.pickup_code not in subject + message
    records = _records(space, order)
    assert records.count() == 1
    assert records.get().actor_id == seller.pk and records.get().meta["event_id"] == event.pk
    changed = ShopOrder.objects.get(pk=order.pk)
    assert (changed.status, changed.pickup_code, changed.amount_due, changed.expires_at, changed.paid_at,
            changed.ready_at) == (order.status, order.pickup_code, order.amount_due, order.expires_at,
                                  order.paid_at, order.ready_at)
    variant.refresh_from_db()
    assert (variant.on_hand, variant.held) == stock
    assert list(order.holds.order_by("pk").values()) == holds
    same_payment = payment_for(order)
    assert (same_payment.pk, same_payment.status, same_payment.amount) == (payment.pk, payment.status, payment.amount)
    assert not RefundCase.objects.filter(payment=payment).exists()
    buyer_read = client(buyer).get(f"/api/v1/member/shop/orders/{order.pk}/")
    assert buyer_read.status_code == 200
    assert buyer_read.json()["pickup_at"] == "space"
    assert not buyer_read.json()["pickup_requires_staff_confirmation"]

    collect_payment(changed, actor=seller, method="cash", hand_over=True)
    terminal_replay = client(seller).post(path)
    assert terminal_replay.status_code == 200, terminal_replay.content
    assert terminal_replay.json()["status"] == "collected"
    assert records.count() == 1 and len(attempts) == 1


def test_events_module_off_lets_the_desk_move_the_pickup(monkeypatch):
    space, _actor, _buyer, event, _variant, order, path = _event_order("move-events-off")
    Makerspace.objects.filter(pk=space.pk).update(
        enabled_modules=sorted(set(space.enabled_modules or []) - {"events"}))
    attempts = _observe(monkeypatch)
    response = client(shop_manager(space)).post(path)
    assert response.status_code == 200, response.content
    assert response.json()["pickup_at"] == "space"
    assert len(attempts) == 1
    assert _records(space, order).get().meta == {"from": "event", "to": "space", "event_id": event.pk}


def test_an_order_collected_at_its_event_is_never_moved_afterwards(monkeypatch):
    space, actor, _buyer, event, _variant, order, path = _event_order("move-after-collect")
    seller = shop_manager(space)
    collect_payment(order, actor=seller, method="cash", hand_over=True)
    cancel(event, actor=actor, notify=False)
    attempts = _observe(monkeypatch)
    response = client(seller).post(path)
    assert response.status_code == 409, response.content
    assert response.json()["code"] == "pickup_change_unavailable"
    order.refresh_from_db()
    assert (order.status, order.pickup_at, order.pickup_event_id) == ("collected", "event", event.pk)
    assert not attempts and not _records(space, order).exists()
