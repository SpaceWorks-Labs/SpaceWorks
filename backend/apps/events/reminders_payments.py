"""Order checkout sweeps (release 2 L6, G28/G33), beside L2's `reminders.py` (never edited).

One beat task, three bounded passes, each order in its own event write boundary:

* expired holds: a checkout that lapsed releases its seats, voids the pending charge
  (expiring the hosted page) and tells the buyer (abandoned checkout). If the money had
  in fact arrived, the order is settled instead;
* missed settlements: a pending order whose charge is settled is seated (the post-commit
  hook failed or the worker restarted);
* payment reminders: an order with no hold (`events.seat_holds` off) still unpaid after a
  day gets ONE reminder -- only where L5's `billing.reminders` is off, so nobody hears twice.
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from apps.audit.services import record
from apps.operations.cloud_jobs import bounded

from .models import EventCheckoutHold, EventOrder
from .services_write_boundary import event_write

logger = logging.getLogger(__name__)
REMINDER_AFTER = timedelta(hours=24)


def _target(order):
    return order.series if order.series_id else order.event


def expire(order_id):
    order = EventOrder.objects.select_related("event", "series").get(pk=order_id)
    if order.series_id:
        return _expire_series(order.series, actor=None, order_id=order_id)
    return _expire_event(order.event, actor=None, order_id=order_id)


def _expire_locked(order_id, actor):
    from apps.payments.reconciliation import cancel_pending
    from .notices_r2_l6 import order_notice
    from .orders_settlement import SETTLED, order_payment, release_hold, settle_locked
    order = EventOrder.objects.select_for_update().get(pk=order_id)
    if order.status != EventOrder.Status.PENDING:
        return order
    payment = order_payment(order)
    if payment is not None and payment.status in SETTLED:
        return settle_locked(order, actor=actor)
    release_hold(getattr(order, "hold", None), EventCheckoutHold.Reason.EXPIRED)
    order.status, order.closed_at = EventOrder.Status.EXPIRED, timezone.now()
    order.save(update_fields=["status", "closed_at"])
    if payment is not None:
        cancel_pending(makerspace=order.makerspace, subject_type="event_order", subject_id=order.pk, actor=actor)
    record(actor, "event.order_expired", makerspace=order.makerspace, target=order, meta={"order_id": order.pk})
    order_notice(order, "order_abandoned")
    return order


@event_write
def _expire_event(event, *, actor, order_id):
    return _expire_locked(order_id, actor)


@event_write
def _expire_series(series, *, actor, order_id):
    return _expire_locked(order_id, actor)


def due_expiries(limit):
    from apps.makerspaces.scheduled_scope import live_space_ids
    return list(EventCheckoutHold.objects.filter(
        released_at__isnull=True, expires_at__lte=timezone.now(), order__status=EventOrder.Status.PENDING,
        order__makerspace_id__in=live_space_ids("events.orders"),
    ).order_by("expires_at").values_list("order_id", flat=True)[:limit])


def missed_settlements(limit):
    # Not switch-gated (#183B money-in-flight exemption): the payer has already paid,
    # so the order settles even if the space switched ticket orders off since.
    from apps.payments.models import Payment
    from .orders_settlement import SETTLED
    paid = Payment.objects.filter(subject_type="event_order", status__in=SETTLED).values("subject_id")
    return list(EventOrder.objects.filter(status=EventOrder.Status.PENDING, pk__in=paid)
                .order_by("pk").values_list("pk", flat=True)[:limit])


def due_reminders(limit):
    from apps.makerspaces.scheduled_scope import live_space_ids
    cutoff = timezone.now() - REMINDER_AFTER
    return list(EventOrder.objects.filter(status=EventOrder.Status.PENDING, hold__isnull=True,
                                          makerspace_id__in=live_space_ids("events.orders"),
                                          reminded_at__isnull=True, created_at__lte=cutoff)
                .order_by("pk").values_list("pk", flat=True)[:limit])


def remind(order_id):
    from apps.makerspaces.platform import feature_enabled
    from .notices_r2_l6 import order_notice
    order = EventOrder.objects.select_related("makerspace", "event", "series").get(pk=order_id)
    stamped = EventOrder.objects.filter(pk=order.pk, reminded_at__isnull=True).update(reminded_at=timezone.now())
    if stamped and not feature_enabled(order.makerspace, "billing.reminders"):
        order_notice(order, "order_payment_reminder", revision="reminder")
    return bool(stamped)


@shared_task
def sweep_order_checkouts_task(limit=50):
    from .orders_settlement import settle_paid_order
    done = 0
    for label, ids, run in (("expire", due_expiries, expire), ("settle", missed_settlements, settle_paid_order),
                            ("remind", due_reminders, remind)):
        for order_id in bounded.items(ids(bounded.rows(limit))):
            try:
                run(order_id)
                done += 1
            except Exception:
                logger.warning("event_order_sweep_failed", extra={"order_id": order_id, "pass": label})
    return done
