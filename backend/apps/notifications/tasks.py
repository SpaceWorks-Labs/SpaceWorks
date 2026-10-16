"""Member push workers and five-minute lease recovery for both scheduler modes."""

import logging

from celery import shared_task
from django.utils import timezone

from apps.accounts import rbac
from apps.notifications.member_push_leases import due_deliveries
from apps.notifications.models_push import MemberPushDelivery
from apps.tenant_migration.gate_runtime import fanout_tenant_write

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=4)
def deliver_member_push(self, row_id):
    from apps.notifications.member_push import deliver_row

    if deliver_row(row_id):
        # The database budget is authoritative even across sweep-created tasks.
        raise self.retry(countdown=min(60 * 2 ** self.request.retries, 300))


@shared_task
def sweep_member_push():
    from apps.notifications.member_push import enqueue_member_push

    now = timezone.now()
    due = due_deliveries(MemberPushDelivery.objects.all(), now).filter(inbox_row__audience="member")
    spaces = due.order_by().values_list("inbox_row__makerspace_id", flat=True).distinct()
    counts = {"enqueued": 0, "skipped": 0, "failed": 0}
    for space_id in spaces.iterator():
        try:
            with fanout_tenant_write(space_id, operation="member_push_recovery", counts=counts) as permitted:
                if not permitted:
                    continue
                rows = rbac.scope_notification_policy(
                    due, makerspace_id=space_id, field="inbox_row__makerspace_id",
                ).order_by().values_list("inbox_row_id", flat=True).distinct()
                for row_id in rows.iterator():
                    if enqueue_member_push(row_id):
                        counts["enqueued"] += 1
                    else:
                        counts["failed"] += 1
        except Exception as exc:
            counts["failed"] += 1
            logger.warning("member_push_sweep_failed", extra={
                "makerspace_id": space_id, "failure_type": type(exc).__name__,
            })
    return counts
