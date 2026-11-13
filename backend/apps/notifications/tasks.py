"""Legacy task IDs are inert; recovery always re-enters the canonical envelope worker."""
import logging

from celery import shared_task
from django.db.models import Q
from django.utils import timezone

from apps.accounts import rbac
from apps.integrations.notification_cutover import boundary, sending_allowed
from apps.notifications.envelope_push_leases import due_deliveries, hold_expired
from apps.notifications.models_push import MemberPushDelivery
from apps.tenant_migration.gate_runtime import fanout_tenant_write

logger = logging.getLogger(__name__)


@shared_task
def deliver_member_push(row_id):
    # Retain the old broker task name, without interpreting inbox IDs as new IDs.
    return False


@shared_task
def sweep_member_push():
    counts = {"enqueued": 0, "skipped": 0, "failed": 0}
    with boundary():
        if not sending_allowed():
            return counts
        candidates = MemberPushDelivery.objects.filter(
            envelope_delivery__channel="native_push", envelope_delivery__historical=False,
        )
        spaces = candidates.order_by().values_list("envelope_delivery__makerspace_id", flat=True).distinct()
        for space_id in spaces.iterator():
            try:
                with fanout_tenant_write(space_id, operation="member_push_recovery", counts=counts) as permitted:
                    if not permitted:
                        continue
                    children = rbac.scope_notification_policy(
                        candidates, makerspace_id=space_id, field="envelope_delivery__makerspace_id",
                    )
                    hold_expired(children)
                    # Unknown outcomes quarantine the parent too, preventing fallback/retry.
                    from apps.integrations.models_contract import NotificationDelivery
                    NotificationDelivery.objects.filter(
                        pk__in=children.filter(status="held").values("envelope_delivery_id"),
                    ).exclude(state__in=["sent", "accepted", "delivered", "read"]).update(
                        state="held", retryable=False, next_attempt_at=None, last_error="ambiguous_timeout",
                        updated_at=timezone.now(),
                    )
                    due = due_deliveries(children).filter(envelope_delivery__state="retrying").filter(
                        Q(envelope_delivery__next_attempt_at=None) |
                        Q(envelope_delivery__next_attempt_at__lte=timezone.now()),
                    )
                    from apps.notifications.member_push import enqueue_parent
                    for parent_id in due.order_by().values_list("envelope_delivery_id", flat=True).distinct().iterator():
                        counts["enqueued" if enqueue_parent(parent_id) else "failed"] += 1
            except Exception as exc:
                counts["failed"] += 1
                logger.warning("member_push_sweep_failed", extra={
                    "makerspace_id": space_id, "failure_type": type(exc).__name__,
                })
    return counts
