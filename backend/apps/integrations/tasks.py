from .notification_cutover import guarded
import random

# Register the shared worker even when no separable domain adapter is installed.
from .broadcasts_worker import broadcast_batch, resume_broadcasts  # noqa: F401
from .notification_tasks import deliver_envelope, sweep_notification_outbox  # noqa: F401

from celery import shared_task
from django.db import transaction

from apps.integrations.dispatch import _deliver
from apps.integrations.health import record_worker_heartbeat
from apps.integrations.models import (
    EmailLog,
    NotificationDeliveryLog,
    NotificationDeliveryStatus,
)
from apps.integrations.smtp_validation import (
    email_task_hard_limit,
    email_task_soft_limit,
    sending_claim_is_stale,
)


@shared_task(
    bind=True,
    max_retries=3,
    soft_time_limit=email_task_soft_limit(),
    time_limit=email_task_hard_limit(),
)
@guarded(sending=True)
def deliver_email_task(self, log_id):
    record_worker_heartbeat()
    log = _claim_log(log_id)
    if log is None:
        return
    _deliver(log)
    log.refresh_from_db()
    if log.status == EmailLog.Status.FAILED:
        try:
            raise self.retry(countdown=_retry_countdown(self.request.retries))
        except self.MaxRetriesExceededError:
            return


def _retry_countdown(retries):
    # Celery remains at-least-once: a worker crash after SMTP accepts the message but
    # before SENT is committed can still resend. The SENDING claim narrows duplicate
    # delivery and stale claims are reclaimed after the hard task limit.
    base = min(60 * (2**retries), 15 * 60)
    return base + random.randint(0, min(base, 30))


def _claim_log(log_id):
    with transaction.atomic():
        candidate = EmailLog.objects.only("makerspace_id").filter(pk=log_id).first()
        if candidate is None:
            return None
        from apps.encryption.write_fence import assert_mapped_write_allowed

        assert_mapped_write_allowed(candidate.makerspace_id)
        log = EmailLog.objects.select_for_update().filter(pk=log_id).first()
        if log is None or log.status in (EmailLog.Status.SENT, EmailLog.Status.SKIPPED):
            return None
        from .mail_providers.outbox import claim_due
        from .mail_retry_policy import unresolved_acceptance
        if unresolved_acceptance(log) or not claim_due(log):
            return None
        from .broadcasts_delivery import attempt_limit
        from .broadcasts_registry import ADAPTERS
        # Duplicate tasks must leave exhausted failures available for manual retry.
        # Only that locked retry renews the budget, including subsequent retries.
        if (log.status == EmailLog.Status.FAILED and log.source_kind in ADAPTERS
                and log.attempts >= attempt_limit(log)):
            return None
        if log.status == EmailLog.Status.SENDING and not sending_claim_is_stale(log):
            return None
        log.status = EmailLog.Status.SENDING
        log.error = ""
        log.save(update_fields=["status", "error", "updated_at"])
        return log


@shared_task(
    bind=True,
    max_retries=3,
    soft_time_limit=email_task_soft_limit(),
    time_limit=email_task_hard_limit(),
)
@guarded(sending=True)
def deliver_notification_task(self, log_id):
    record_worker_heartbeat()
    log = _claim_notification_log(log_id)
    if log is None:
        return
    from apps.integrations.dispatch_channels import _deliver_notification

    _deliver_notification(log)
    log.refresh_from_db()
    if _should_retry_notification(log):
        try:
            raise self.retry(countdown=_retry_countdown(self.request.retries))
        except self.MaxRetriesExceededError:
            return


def _should_retry_notification(log) -> bool:
    # Retry only real provider-delivery failures. A delivery-time
    # "notification_channel_not_configured" (destination cleared after enqueue) is
    # terminal — retrying wastes attempts and could deliver a stale notification if the
    # destination is reconfigured mid-backoff. Cap/not-configured dispatch rows are never
    # enqueued, so they never reach here.
    return log.status == NotificationDeliveryStatus.FAILED and log.error.startswith(
        "notification_delivery_failed"
    )


def _claim_notification_log(log_id):
    with transaction.atomic():
        log = (
            NotificationDeliveryLog.objects.select_for_update()
            .filter(pk=log_id)
            .first()
        )
        if log is None or log.status in (NotificationDeliveryStatus.SENT, NotificationDeliveryStatus.SKIPPED):
            return None
        from .mail_providers.budget_config import free_profile
        if free_profile() and log.attempts >= 4:
            return None
        if (
            log.status == NotificationDeliveryStatus.SENDING
            and not sending_claim_is_stale(log)
        ):
            return None
        log.status = NotificationDeliveryStatus.SENDING
        log.error = ""
        log.save(update_fields=["status", "error", "updated_at"])
        return log

from .tasks_messaging_settings import wipe_messaging_credentials_task  # noqa: F401

from .tasks_messaging import canonical_retention_task, deliver_messaging_task, sweep_messaging_task  # noqa: F401
