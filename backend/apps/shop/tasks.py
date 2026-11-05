"""The shop sweep (one beat task, bounded passes; registered in the cloud-jobs catalogue).

* lapsed: an unpaid online order past its window is cancelled and its hold released (a
  charge that did settle is sold instead);
* missed settlements: an open order whose charge settled is sold (the post-commit hook
  failed or a worker restarted);
* uncollected reminders (Q-S17): a paid order not yet collected gets a reminder at the
  space's first and second reminder days (3 and 7 by default).
Only spaces with the `shop` module on are touched; with it off nothing runs (#95).
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.db.models import F
from django.utils import timezone

from apps.operations.cloud_jobs import bounded

from .models import ShopOrder, ShopSettings

logger = logging.getLogger(__name__)


def _live(queryset):
    from apps.makerspaces.models import Makerspace
    from apps.makerspaces.servability import servable_queryset

    spaces = servable_queryset(Makerspace.objects.filter(enabled_modules__contains=["shop"])).values("pk")
    return queryset.filter(makerspace_id__in=spaces)


def due_lapses(limit):
    return list(_live(ShopOrder.objects.filter(status__in=ShopOrder.OPEN_STATUSES, channel=ShopOrder.Channel.ONLINE,
                                               expires_at__lte=timezone.now()))
                .order_by("expires_at").values_list("pk", flat=True)[:limit])


def missed_settlements(limit):
    from apps.payments.models import Payment

    from .settlement import SETTLED

    paid = Payment.objects.filter(subject_type="shop_order", status__in=SETTLED).values("subject_id")
    return list(_live(ShopOrder.objects.filter(status__in=ShopOrder.OPEN_STATUSES, pk__in=paid))
                .order_by("pk").values_list("pk", flat=True)[:limit])


def due_reminders(limit):
    return list(_live(ShopOrder.objects.filter(status__in=ShopOrder.PAID_STATUSES, paid_at__isnull=False,
                                               reminders_sent__lt=2))
                .order_by("paid_at").values_list("pk", flat=True)[:limit])


def remind(order_id):
    from .notices import buyer_notice

    order = ShopOrder.objects.select_related("makerspace").get(pk=order_id)
    row = ShopSettings.for_makerspace(order.makerspace)
    days = (row.first_reminder_days, row.second_reminder_days)[order.reminders_sent]
    if timezone.now() < order.paid_at + timedelta(days=days):
        return False
    stamped = ShopOrder.objects.filter(pk=order.pk, reminders_sent=order.reminders_sent).update(
        reminders_sent=F("reminders_sent") + 1)
    if stamped:
        buyer_notice(order, "shop_order_reminder", marker=f"reminder-{order.reminders_sent + 1}")
    return bool(stamped)


@shared_task
def sweep_shop_task(limit=50):
    from .services_orders import lapse
    from .settlement import settle_paid_order

    done = 0
    for label, ids, run in (("lapse", due_lapses, lapse), ("settle", missed_settlements, settle_paid_order),
                            ("remind", due_reminders, remind)):
        for order_id in bounded.items(ids(bounded.rows(limit))):
            try:
                run(order_id)
                done += 1
            except Exception:  # noqa: BLE001 - one order never stops the sweep
                logger.warning("shop_sweep_failed", extra={"order_id": order_id, "pass": label})
    return done
