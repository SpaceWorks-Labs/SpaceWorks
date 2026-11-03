"""The buyer abandons an unpaid order (release 2 L6, G28): seats back on sale, charge voided.

Only a PENDING order can be abandoned. A paid one is not undone here: its seats are
cancelled one registration at a time, each through the refund policy (`orders_refunds`).
If the charge turns out to be settled already, the order is seated instead.
"""

from django.utils import timezone

from apps.audit.services import record

from .models import EventCheckoutHold, EventOrder
from .orders_errors import OrderRefused
from .services_write_boundary import event_write


def _cancel_locked(order_id, actor):
    from apps.payments.reconciliation import cancel_pending
    from .orders_settlement import SETTLED, order_payment, release_hold, settle_locked
    order = EventOrder.objects.select_for_update().get(pk=order_id)
    if order.status != EventOrder.Status.PENDING:
        raise OrderRefused("order_not_payable", "Only an unpaid order can be abandoned.")
    payment = order_payment(order)
    if payment is not None and payment.status in SETTLED:
        return settle_locked(order, actor=actor)
    release_hold(EventCheckoutHold.objects.filter(order=order).first(), EventCheckoutHold.Reason.CANCELLED)
    order.status, order.closed_at = EventOrder.Status.CANCELLED, timezone.now()
    order.save(update_fields=["status", "closed_at"])
    if payment is not None:
        cancel_pending(makerspace=order.makerspace, subject_type="event_order", subject_id=order.pk, actor=actor)
    record(actor, "event.order_cancelled", makerspace=order.makerspace, target=order,
           meta={"order_id": order.pk, "reason": "buyer"})
    return order


@event_write
def _cancel_event(event, *, actor, order_id):
    return _cancel_locked(order_id, actor)


@event_write
def _cancel_series(series, *, actor, order_id):
    return _cancel_locked(order_id, actor)


def cancel_pending_order(order, *, actor):
    if order.series_id:
        return _cancel_series(order.series, actor=actor, order_id=order.pk)
    return _cancel_event(order.event, actor=actor, order_id=order.pk)
