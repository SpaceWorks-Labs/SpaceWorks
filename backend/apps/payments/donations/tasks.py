"""Lane L18 beat tasks, registered in the cloud-jobs catalogue (the free tick, X-7).

* `raise_pledges_task` -- a bounded batch of pledges whose period is due raises its gift and
  charge (idempotent per period) and reminds the giver.
* `remind_perks_task` -- sponsor perks due within a week and not fulfilled tell staff once.
Both skip spaces whose switch is off, so switching off stops the jobs and keeps the data.
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from apps.operations.cloud_jobs import bounded

logger = logging.getLogger(__name__)
PERK_NOTICE_DAYS = 7


@shared_task
def raise_pledges_task(limit=100):
    from .pledges import due_pledge_ids, raise_one

    today, done = timezone.localdate(), 0
    for pledge_id in bounded.items(due_pledge_ids(bounded.rows(limit), today)):
        try:
            done += bool(raise_one(pledge_id, today))
        except Exception as exc:  # noqa: BLE001 - one bad pledge never stops the batch
            logger.warning("pledge_raise_failed", extra={"pledge_id": pledge_id, "failure_type": type(exc).__name__})
    return done


def due_perk_ids(limit, today):
    from .models import SponsorPerk
    from apps.makerspaces.scheduled_scope import live_space_ids

    return list(SponsorPerk.objects.filter(
        makerspace_id__in=live_space_ids("finance.sponsors"),
        sponsor__isnull=False, sponsor__archived_at__isnull=True, fulfilled_at__isnull=True, reminded_on__isnull=True,
        due_on__isnull=False, due_on__lte=today + timedelta(days=PERK_NOTICE_DAYS),
    ).order_by("due_on", "pk").values_list("pk", flat=True)[:limit])


def remind_perk(perk_id, today):
    from apps.makerspaces.platform import feature_enabled
    from apps.tenant_migration.gate_runtime import tenant_write

    from .models import SponsorPerk
    from .notices import notify_perk_due

    perk = SponsorPerk.objects.select_related("makerspace").get(pk=perk_id)
    if not feature_enabled(perk.makerspace, "finance.sponsors"):
        return False
    with tenant_write(perk.makerspace_id):
        if not SponsorPerk.objects.filter(pk=perk.pk, reminded_on__isnull=True).update(reminded_on=today):
            return False
        notify_perk_due(perk)
    return True


@shared_task
def remind_perks_task(limit=100):
    today, done = timezone.localdate(), 0
    for perk_id in bounded.items(due_perk_ids(bounded.rows(limit), today)):
        try:
            done += remind_perk(perk_id, today)
        except Exception as exc:  # noqa: BLE001
            logger.warning("perk_reminder_failed", extra={"perk_id": perk_id, "failure_type": type(exc).__name__})
    return done
