"""Decision 221(f): the shop buyer hears their order was handed over (the pickup "delivered" notice)."""
import pytest

from apps.integrations.models_contract import NotificationEnvelope
from apps.integrations.notification_catalog import FEATURE_EVENTS
from apps.shop.notices import BUYER_EVENTS, eligible
from apps.shop.services_orders import collect

from .helpers import shop_manager, shop_space
from .test_hold_return_refund_coordination import _paid_online
from .helpers import product

pytestmark = pytest.mark.django_db(transaction=True)


def test_collection_tells_an_account_buyer_once_and_the_event_is_catalogued():
    assert "shop_order_collected" in BUYER_EVENTS
    assert "shop_order_collected" in FEATURE_EVENTS["payments"]
    space = shop_space("n221-collect", "shop.online", "shop.holds")
    seller = shop_manager(space)
    _row, variant = product(space, seller, stock=3)
    order = _paid_online(space, variant, qty=1, buyer="n221-buyer")
    collect(order, actor=seller, code=order.pickup_code)
    rows = list(NotificationEnvelope.objects.filter(event="shop_order_collected", source_id=str(order.pk)))
    assert [(row.recipient_id, row.audience) for row in rows] == [(order.buyer_id, "requester")]
    assert eligible(rows[0])
