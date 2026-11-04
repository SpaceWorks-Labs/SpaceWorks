"""The job flow's clock (#142 OQ-2/OQ-3/OQ-7): quote reminders and expiry, prepaid jobs
joining the queue, and pickup reminders on days 3 and 10.

Bounded per tick; every row runs inside its own skip-and-count tenant boundary. Marking
a job Not collected stays a staff action (OQ-7: a person confirms), so nothing here
ends a finished job.
"""

import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.accounts import rbac
from apps.machines import job_policy
from apps.machines.models import MachineServiceRequest as Job

logger = logging.getLogger(__name__)
LIMIT = 200


def _rows(queryset):
    return rbac.scope_for_scheduled_work(queryset.filter(
        makerspace__enabled_features__contains=[job_policy.JOB_REQUESTS])).order_by("pk")[:LIMIT]


def _each(rows, operation, counts, work):
    from apps.operations.cloud_jobs import bounded
    from apps.tenant_migration.gate_runtime import fanout_tenant_write
    for row in bounded.page(rows, "machine-job-flow"):
        with fanout_tenant_write(row.makerspace_id, operation=operation, counts=counts) as go:
            if not go:
                continue
            try:
                counts[operation] = counts.get(operation, 0) + int(bool(work(row)))
            except Exception:
                counts["skipped"] = counts.get("skipped", 0) + 1
                logger.exception("machine_job_sweep_failed", extra={"operation": operation, "job_id": row.pk})


def _remind_quote(row):
    from apps.machines.notifications_job_flow import notify_job
    with transaction.atomic():
        claimed = Job.objects.filter(pk=row.pk, status=Job.Status.QUOTED, quote_reminded_at__isnull=True,
                                     quote_approved_at__isnull=True).update(quote_reminded_at=timezone.now())
        if claimed:
            row.refresh_from_db()
            notify_job(row, "quote_reminder")
        return claimed


def _remind_pickup(row, stage):
    from apps.machines.notifications_job_flow import notify_job
    with transaction.atomic():
        claimed = Job.objects.filter(pk=row.pk, status=Job.Status.COMPLETED,
                                     pickup_reminders_sent=stage - 1).update(pickup_reminders_sent=stage)
        if claimed:
            row.refresh_from_db()
            notify_job(row, "pickup_reminder")
        return claimed


def run_job_flow_sweep(*, now=None):
    from apps.machines.service_workflow_review import decline_quote, promote_prepaid
    now = now or timezone.now()
    counts = {"skipped": 0}
    quoted = Job.objects.filter(status=Job.Status.QUOTED, quote_approved_at__isnull=True)
    _each(_rows(quoted.filter(quote_expires_at__lte=now)), "quote_expired", counts,
          lambda row: decline_quote(row, None, expired=True))
    due = now - timedelta(days=job_policy.QUOTE_REMINDER_DAY)
    _each(_rows(quoted.filter(quote_reminded_at__isnull=True, quoted_at__lte=due, quote_expires_at__gt=now)),
          "quote_reminder", counts, _remind_quote)
    awaiting = Job.objects.filter(status=Job.Status.QUOTED, prepay=True, quote_approved_at__isnull=False)
    _each(_rows(awaiting), "prepaid_queued", counts, lambda row: promote_prepaid(row))
    for stage, days in enumerate(job_policy.PICKUP_REMINDER_DAYS, start=1):
        ready = Job.objects.filter(status=Job.Status.COMPLETED, pickup_reminders_sent=stage - 1,
                                   completed_at__lte=now - timedelta(days=days))
        _each(_rows(ready), f"pickup_reminder_{stage}", counts, lambda row, s=stage: _remind_pickup(row, s))
    return counts
