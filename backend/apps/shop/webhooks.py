"""Shop order fulfilment status for signed webhook destinations (decision 221(h)).

Outbound only, and for destinations alone: the buyer's own notices are `notices.py`. Each event
carries ids and the event time -- `shop_order_id` plus the makerspace -- never a buyer, an item,
a pickup code or an amount, so a destination fetches detail through the API if it needs any.

* `shop_order_ready_for_pickup` -- staff put a paid order on the shelf.
* `shop_order_picked_up` -- handed over at the space.
* `shop_order_delivered` -- handed over at the event the buyer chose (this shop never ships).
* `shop_order_pickup_moved` -- an unavailable event pickup was moved to the space.

Fail safe: a missing destination, a switched-off webhook cell or a failed insert never blocks the
order workflow. Called inside the domain transaction, so a rolled-back transition emits nothing.
"""

import logging

from django.db import transaction
from django.utils import timezone
from apps.integrations.fanout_jobs import deferred_fanout

logger = logging.getLogger(__name__)

EVENTS = ("shop_order_ready_for_pickup", "shop_order_picked_up", "shop_order_delivered", "shop_order_pickup_moved")
_TEXT = {
    "shop_order_ready_for_pickup": "Shop order #{} is ready for pickup.",
    "shop_order_picked_up": "Shop order #{} was picked up.",
    "shop_order_delivered": "Shop order #{} was delivered at its event.",
    "shop_order_pickup_moved": "Shop order #{} pickup was moved to the space.",
}


def handover_event(order):
    """`delivered` for an order handed over at its event, else `picked_up`."""
    return "shop_order_delivered" if order.pickup_at == "event" else "shop_order_picked_up"


@deferred_fanout()
def order_webhook(order, event):
    """Queue `payments.<event>` to the space's webhook destinations; False when nothing was queued."""
    from apps.integrations.dispatch_channels import dispatch_channel
    from apps.integrations.notification_catalog import is_notification_enabled
    from apps.makerspaces.platform import module_enabled
    from apps.makerspaces.servability import is_servable

    if event not in EVENTS:
        raise ValueError("Unknown shop webhook event")
    space = order.makerspace
    try:
        if not (is_servable(space) and module_enabled(space, "shop")
                and is_notification_enabled(space, "payments", "webhook")):
            return False
        with transaction.atomic():  # a failed INSERT rolls back its savepoint, not the order
            dispatch_channel(makerspace=space, channel="webhook", feature="payments", event=event,
                             text_body=_TEXT[event].format(order.pk),
                             payload={"shop_order_id": order.pk, "occurred_at": timezone.now().isoformat()})
        return True
    except Exception as exc:
        logger.warning("shop_webhook_failed", extra={"makerspace_id": space.pk, "event": event,
                                                     "failure_type": type(exc).__name__})
        return False
