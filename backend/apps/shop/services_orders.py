"""Order lifecycle after placement: ready, collected, cancelled, lapsed (release 2 L22).

* `mark_ready` -- staff put a paid order on the pickup shelf; the buyer hears.
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
    order.status, order.collected_at, order.collected_by = ShopOrder.Status.COLLECTED, timezone.now(), actor
    order.save(update_fields=["status", "collected_at", "collected_by"])
    audit.record(actor, "shop.order_collected", makerspace=order.makerspace, target=order,
                 meta={"order_id": order.pk, "pickup_at": order.pickup_at})
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
    return_shop_stock(order, order_pairs(order), actor=actor, reason="Uncollected order cancelled")
    order.status, order.closed_at, order.close_reason = ShopOrder.Status.CANCELLED, timezone.now(), "uncollected"
    order.save(update_fields=["status", "closed_at", "close_reason"])
    case = _due_full(order, actor, "shop_uncollected")
    audit.record(actor, "shop.order_cancelled", makerspace=order.makerspace, target=order, meta={
        "order_id": order.pk, "reason": "uncollected", "case_id": getattr(case, "pk", None),
        "note_given": bool(reason)})
    buyer_notice(order, "shop_order_cancelled")
    return order
