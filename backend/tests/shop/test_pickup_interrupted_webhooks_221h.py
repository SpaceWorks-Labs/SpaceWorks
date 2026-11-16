"""Decision 221(h): interrupted event pickups block handover; a move replay is a no-op; status webhooks."""

import pytest

from apps.events.services_lifecycle import cancel
from apps.integrations.models import NotificationDeliveryLog
from apps.shop.models import ShopOrder
from apps.shop.webhooks import EVENTS, order_webhook

from .helpers import client, shop_manager
from .test_move_event_pickup import _event_order

pytestmark = pytest.mark.django_db


def test_staff_cannot_hand_over_an_interrupted_event_pickup_until_it_is_moved():
    space, actor, _buyer, event, _variant, order, move = _event_order("interrupted-221h")
    ShopOrder.objects.filter(pk=order.pk).update(status="paid")
    seller = shop_manager(space)
    collect = f"/api/v1/admin/shop/orders/{order.pk}/collect/"
    cancel(event, actor=actor, notify=False)
    refused = client(seller).post(collect, {"pickup_code": order.pickup_code}, format="json")
    assert refused.status_code == 409 and refused.json()["code"] == "pickup_interrupted"
    assert client(seller).post(move).status_code == 200
    done = client(seller).post(collect, {"pickup_code": order.pickup_code}, format="json")
    assert done.status_code == 200 and done.json()["status"] == "collected"


def test_retrying_a_move_on_a_moved_then_cancelled_order_is_a_200_noop():
    space, actor, _buyer, event, _variant, order, move = _event_order("moved-cancelled-221h")
    seller = shop_manager(space)
    cancel(event, actor=actor, notify=False)
    assert client(seller).post(move).status_code == 200
    ShopOrder.objects.filter(pk=order.pk).update(status="cancelled")
    again = client(seller).post(move)
    assert again.status_code == 200 and again.json()["pickup_at"] == "space"


def test_status_events_are_registered_for_webhook_v2_with_an_id_only_schema():
    from apps.integrations.webhook_schema import schema_catalog
    definitions = schema_catalog()["$defs"]
    for name in EVENTS:
        data = definitions[f"payments.{name}"]["properties"]["data"]
        assert data["additionalProperties"] is False and "shop_order_id" in data["properties"]


def test_order_webhook_queues_ids_only_and_stays_off_when_the_webhook_cell_is_off(monkeypatch):
    space, _actor, _buyer, _event, _variant, order, _move = _event_order("webhook-221h")
    order = ShopOrder.objects.select_related("makerspace", "buyer").get(pk=order.pk)
    from apps.integrations import notification_catalog
    monkeypatch.setattr(notification_catalog, "is_notification_enabled", lambda *args: False)
    assert order_webhook(order, "shop_order_ready_for_pickup") is False
    monkeypatch.setattr(notification_catalog, "is_notification_enabled", lambda *args: True)
    assert order_webhook(order, "shop_order_ready_for_pickup") is True
    row = NotificationDeliveryLog.objects.get(makerspace=space, event="shop_order_ready_for_pickup")
    assert row.feature == "payments" and row.channel == "webhook"
    assert row.payload["shop_order_id"] == order.pk
    assert order.pickup_code not in row.text_body and order.buyer.username not in row.text_body
