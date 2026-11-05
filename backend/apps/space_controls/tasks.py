"""Space-control beat work (#185): scheduled archive/purge with reminders, and the
announcement emails. Each step is bounded and catches its own failure so one space can
never stop the sweep for the others."""

import logging

from celery import shared_task
from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)
BATCH = 50


def run_schedules(now=None):
    from .models import SpaceControlState
    from .schedule_mail import send_reminder
    from .services_schedule import run_archive, run_purge

    now = now or timezone.now()
    counts = {"archived": 0, "purged": 0, "reminded": 0, "failed": 0}
    due_archives = SpaceControlState.objects.filter(archive_on__lte=now).values_list("pk", flat=True)[:BATCH]
    for state_id in list(due_archives):
        counts["archived"] += _step(lambda pk: run_archive(pk, now), state_id, counts)
    upcoming = SpaceControlState.objects.filter(
        Q(archive_on__gt=now) | Q(purge_due_at__gt=now),
    ).select_related("makerspace").order_by("pk")[:BATCH * 4]
    for state in upcoming:
        counts["reminded"] += _step(lambda _id, row=state: send_reminder(row, now), state.pk, counts)
    due_purges = SpaceControlState.objects.filter(purge_due_at__lte=now).values_list("pk", flat=True)[:BATCH]
    for state_id in list(due_purges):
        counts["purged"] += _step(lambda pk: run_purge(pk, now), state_id, counts)
    logger.info("space_control_schedules_swept", extra=counts)
    return counts


def _step(callable_, state_id, counts):
    try:
        return int(bool(callable_(state_id)))
    except Exception:
        counts["failed"] += 1
        logger.exception("space_control_schedule_step_failed", extra={"control_state_id": state_id})
        return 0


@shared_task(name="apps.space_controls.tasks.run_space_schedules_task")
def run_space_schedules_task():
    return run_schedules()


@shared_task(name="apps.space_controls.tasks.send_announcement_emails_task")
def send_announcement_emails_task():
    from .announcements import send_due_emails

    return send_due_emails()
