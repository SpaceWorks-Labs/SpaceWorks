"""Order lifecycle after placement: ready, collected, cancelled, lapsed (release 2 L22).

* `mark_ready` -- staff put a paid order on the pickup shelf; the buyer hears.
* `move_event_pickup_to_space` -- the desk (`SELL_SHOP`) moves an active order whose event pickup
  is unavailable to the makerspace, once: audited, one buyer notice, and a replay (even after
  collection or cancellation) is a no-op. Payment, stock, holds and the pickup code are untouched.
* `collect` -- staff hand it over at the desk (or at an event) by its pickup code; audited
  with who collected it. No evidence photo (Q-S3, Q-S17).
* `cancel_unpaid` -- the buyer or staff abandon an order that is not paid: its hold goes
  back and its pending charge is voided; no money moves.
* `cancel_uncollected` -- Q-S17: a PAID order nobody collected may be cancelled by staff
  after the space's window (30 days); its stock goes back on the shelf and a refund case
  opens for staff to approve (#59).
* `lapse` -- the sweep: an unpaid order past its window is cancelled like `cancel_unpaid`.
Every transition is audited with a literal action.
"""

from datetime import timedelta

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.audit import services as audit

from .errors import ShopRefused
from .models import ShopCheckoutHold, ShopOrder, ShopSettings
from .orders_core import order_payment


def _locked(order):
    from .gates import write_allowed

    locked = ShopOrder.objects.select_for_update().select_related("makerspace").get(pk=order.pk)
    write_allowed(locked.makerspace)
    return locked


@transaction.atomic
def mark_ready(order, *, actor):
    from .notices import buyer_notice

    order = _locked(order)
    if order.status != ShopOrder.Status.PAID:
        raise ShopRefused("order_not_collectable", "Only a paid order can be marked ready.")
    order.status, order.ready_at = ShopOrder.Status.READY, timezone.now()
    order.save(update_fields=["status", "ready_at"])
    audit.record(actor, "shop.order_ready", makerspace=order.makerspace, target=order, meta={"order_id": order.pk})
    buyer_notice(order, "shop_order_ready")
    from .webhooks import order_webhook  # decision 221(h): destinations hear it too (ids only)
    order_webhook(order, "shop_order_ready_for_pickup")
    return order


@transaction.atomic
def move_event_pickup_to_space(order, *, actor):
    from apps.audit.models import AuditLog
    from .gates import SELL, staff_space
    from .notices import buyer_notice
    from .pickup_status import pickup_requires_staff_confirmation

    order = _locked(order)
    order.makerspace = staff_space(actor, order.makerspace_id, SELL)
    active = order.status in (*ShopOrder.OPEN_STATUSES, *ShopOrder.PAID_STATUSES)
    # Decision 221(h): a replay is a no-op in ANY later state (collected, or moved then cancelled).
    if order.pickup_at == ShopOrder.Pickup.SPACE:
        if AuditLog.objects.filter(
                makerspace_id=order.makerspace_id, target_type=order._meta.label_lower,
                target_id=str(order.pk), action="shop.order_pickup_moved_to_space").exists():
            return order
    if not active:
        raise ShopRefused("pickup_change_unavailable", "Only an active order can change its pickup.")
    if not pickup_requires_staff_confirmation(order):
        raise ShopRefused("pickup_change_unavailable", "This order does not need an alternate pickup.")
    prior_event = order.pickup_event
    event_id = prior_event.pk if prior_event is not None and prior_event.makerspace_id == order.makerspace_id else None
    order.pickup_at, order.pickup_event = ShopOrder.Pickup.SPACE, None
    order.save(update_fields=["pickup_at", "pickup_event"])
    audit.record(actor, "shop.order_pickup_moved_to_space", makerspace=order.makerspace, target=order,
                 meta={"from": "event", "to": "space", "event_id": event_id})
    buyer_notice(order, "shop_order_pickup_moved_to_space", marker="space")
    from .webhooks import order_webhook
    order_webhook(order, "shop_order_pickup_moved")
    return order


def find_by_code(space, code):
    order = ShopOrder.objects.filter(makerspace=space, pickup_code=str(code or "").strip().upper()).first()
    if order is None:
        raise ShopRefused("pickup_code_invalid", "No order has that pickup code.")
    return order


@transaction.atomic
def collect(order, *, actor, code=None):
    order = _locked(order)
    if code is not None and str(code).strip().upper() != order.pickup_code:
        raise ShopRefused("pickup_code_invalid", "That pickup code does not match this order.")
    if order.status not in ShopOrder.PAID_STATUSES:
        raise ShopRefused("order_not_collectable", "Only a paid order can be collected.", status=order.status)
    from .pickup_status import pickup_requires_staff_confirmation
    if pickup_requires_staff_confirmation(order):  # decision 221(h): move the pickup first
        raise ShopRefused("pickup_interrupted", "This order's event pickup was interrupted. Move the pickup to "
                                                "the space before handing it over.")
    order.status, order.collected_at, order.collected_by = ShopOrder.Status.COLLECTED, timezone.now(), actor
    order.save(update_fields=["status", "collected_at", "collected_by"])
    audit.record(actor, "shop.order_collected", makerspace=order.makerspace, target=order,
                 meta={"order_id": order.pk, "pickup_at": order.pickup_at})
    from .notices import buyer_notice  # decision 221(f): the buyer hears it was handed over
    buyer_notice(order, "shop_order_collected")
    from .webhooks import handover_event, order_webhook
    order_webhook(order, handover_event(order))
    return order


def _close_unpaid(order, actor, reason):
    from apps.inventory.availability import release_shop_hold
    from apps.payments.reconciliation import cancel_pending

    from .settlement import SETTLED, settle_locked

    payment = order_payment(order)
    if payment is not None and payment.status in SETTLED:
        return settle_locked(order, actor=actor)  # the money arrived after all: sell instead
    release_shop_hold(order, ShopCheckoutHold.Reason.EXPIRED if reason == "expired"
                      else ShopCheckoutHold.Reason.CANCELLED)
    order.status, order.closed_at, order.close_reason = ShopOrder.Status.CANCELLED, timezone.now(), reason
    order.save(update_fields=["status", "closed_at", "close_reason"])
    if payment is not None:
        cancel_pending(makerspace=order.makerspace, subject_type="shop_order", subject_id=order.pk, actor=actor)
    audit.record(actor, "shop.order_cancelled", makerspace=order.makerspace, target=order,
                 meta={"order_id": order.pk, "reason": reason})
    return order


@transaction.atomic
def cancel_unpaid(order, *, actor, reason="buyer"):
    order = _locked(order)
    if order.status not in ShopOrder.OPEN_STATUSES:
        raise ShopRefused("order_not_cancellable", "Only an unpaid order can be cancelled here.")
    return _close_unpaid(order, actor, reason)


@transaction.atomic
def lapse(order_id):
    from .notices import buyer_notice

    order = _locked(ShopOrder(pk=order_id))
    if order.status not in ShopOrder.OPEN_STATUSES or not order.expires_at or order.expires_at > timezone.now():
        return order
    order = _close_unpaid(order, None, "expired")
    if order.status == ShopOrder.Status.CANCELLED:
        buyer_notice(order, "shop_order_lapsed")
    return order


@transaction.atomic
def cancel_uncollected(order, *, actor, reason=""):
    from apps.inventory.availability import return_shop_stock

    from .notices import buyer_notice
    from .settlement import _due_full, order_pairs

    order = _locked(order)
    window = timedelta(days=ShopSettings.for_makerspace(order.makerspace).uncollected_cancel_days)
    if order.status not in ShopOrder.PAID_STATUSES or not order.paid_at:
        raise ShopRefused("order_not_cancellable", "Only a paid, uncollected order can be cancelled this way.")
    if timezone.now() < order.paid_at + window:
        raise ShopRefused("order_not_cancellable", "This order can be cancelled once it has waited "
                                                   f"{window.days} days for pickup.")
    # Units a return already took back were restocked or written off, and their share already
    # went to the refund case: neither happens twice (decision 216 item 11).
    return_shop_stock(order, order_pairs(order, remaining=True), actor=actor, reason="Uncollected order cancelled")
    from .consumable_costs import reverse_return_costs
    reverse_return_costs(order, actor=actor)
    order.status, order.closed_at, order.close_reason = ShopOrder.Status.CANCELLED, timezone.now(), "uncollected"
    order.save(update_fields=["status", "closed_at", "close_reason"])
    returned = order.returns.aggregate(total=Sum("amount"))["total"] or 0
    case = _due_full(order, actor, "shop_uncollected", less=returned)
    audit.record(actor, "shop.order_cancelled", makerspace=order.makerspace, target=order, meta={
        "order_id": order.pk, "reason": "uncollected", "case_id": getattr(case, "pk", None),
        "note_given": bool(reason)})
    buyer_notice(order, "shop_order_cancelled")
    return order
