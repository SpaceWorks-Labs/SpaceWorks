"""After a shop order's charge settles: sell its stock and tell the buyer.

The ledger's one settlement seam (`payments.admission_settlement`) hands a settled
`shop_order` here after the payment lock is released (online webhooks, a staff receipt,
a waiver). The order's held stock becomes a sale through the availability module; if the
stock is gone (holds off, or a linked consumable used up in the workshop) the order is
`unfulfilled` and a refund case opens for staff to approve (#59). A failure never rolls
back money received; the sweep retries missed settlements.
"""

import logging

from django.db import transaction
from django.utils import timezone

from apps.audit import services as audit

from .models import ShopOrder
from .orders_core import order_payment

logger = logging.getLogger(__name__)
SETTLED = ("paid_online", "paid_offline", "waived")


def after_settlement(payment):
    if payment.status not in SETTLED:
        return
    order_id = payment.subject_id

    def resume():
        try:
            settle_paid_order(order_id)
        except Exception as exc:  # noqa: BLE001 - logged; the sweep retries
            logger.warning("shop_order_settlement_failed", extra={"order_id": order_id,
                                                                   "failure_type": type(exc).__name__})

    transaction.on_commit(resume)


def settle_paid_order(order_id):
    with transaction.atomic():
        order = ShopOrder.objects.select_for_update().select_related("makerspace").filter(pk=order_id).first()
        if order is None or order.status not in ShopOrder.OPEN_STATUSES:
            return order
        payment = order_payment(order)
        if payment is None or payment.status not in SETTLED:
            return order
        return settle_locked(order, actor=None)


def order_pairs(order):
    """The stock units an order's lines take, with the bundle rule frozen at placement."""
    from apps.inventory.availability import shop_stock_units

    bundles = bool((order.pricing_snapshot or {}).get("bundles"))
    pairs = []
    for line in order.lines.select_related("variant__product"):
        pairs += shop_stock_units(line.variant, line.quantity, bundles=bundles)
    return pairs


def settle_locked(order, *, actor, collect=False):
    """Sell a LOCKED open order's stock and mark it paid (or collected at the desk)."""
    from apps.inventory.availability import OutOfStock, release_shop_hold, sell_shop_stock

    from .models import ShopCheckoutHold
    from .notices import buyer_notice, staff_notice

    now = timezone.now()
    try:
        sell_shop_stock(order, order_pairs(order), actor=actor, reason=f"Shop order #{order.pk}")
    except OutOfStock as exc:
        release_shop_hold(order, ShopCheckoutHold.Reason.CANCELLED)
        order.status, order.paid_at, order.closed_at = ShopOrder.Status.UNFULFILLED, now, now
        order.close_reason = "out_of_stock"
        order.save(update_fields=["status", "paid_at", "closed_at", "close_reason"])
        case = _due_full(order, actor, "shop_unfulfilled")
        audit.record(actor, "shop.order_unfulfilled", makerspace=order.makerspace, target=order, meta={
            "order_id": order.pk, "variant_id": exc.variant_id, "case_id": getattr(case, "pk", None)})
        buyer_notice(order, "shop_order_unfulfilled")
        staff_notice(order.makerspace, order, "shop_order_unfulfilled")
        return order
    order.status, order.paid_at = (ShopOrder.Status.COLLECTED if collect else ShopOrder.Status.PAID), now
    fields = ["status", "paid_at"]
    if collect:
        order.collected_at, order.collected_by = now, actor
        fields += ["collected_at", "collected_by"]
    order.save(update_fields=fields)
    audit.record(actor, "shop.order_paid", makerspace=order.makerspace, target=order,
                 meta={"order_id": order.pk, "total": str(order.amount_due), "channel": order.channel})
    if not collect:
        buyer_notice(order, "shop_order_paid")
    return order


def _due_full(order, actor, reason_code):
    from apps.payments.services_refund_partial import add_due_share

    payment = order_payment(order)
    if payment is None:
        return None
    return add_due_share(payment, amount=payment.amount, reason_code=reason_code, actor=actor,
                         snapshot={"shop_order_id": order.pk})
