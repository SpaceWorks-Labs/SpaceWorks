"""Celery tasks that deliver sealed, never-stored messages (see transient_mail)."""
import logging

from celery import shared_task

from apps.integrations.health import record_worker_heartbeat
from apps.integrations.notification_cutover import guarded
from apps.integrations.smtp_validation import email_task_hard_limit, email_task_soft_limit

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=4, soft_time_limit=email_task_soft_limit(), time_limit=email_task_hard_limit())
@guarded(sending=True)
def deliver_transient_email_task(self, log_id, sealed):
    """Send one sealed email. Idempotent: ``_claim_log`` refuses SENT/SKIPPED/in-flight rows, and an
    unresolved provider acceptance is never re-sent, so a retry or duplicate delivery cannot double-send."""
    from apps.integrations.dispatch import _deliver
    from apps.integrations.models import EmailLog
    from apps.integrations.tasks import _claim_log, _retry_countdown
    from apps.integrations.transient_mail import unseal
    record_worker_heartbeat()
    payload = unseal(sealed)
    if payload is None:
        EmailLog.objects.filter(pk=log_id).exclude(status__in=[EmailLog.Status.SENT, EmailLog.Status.SKIPPED]).update(
            status=EmailLog.Status.FAILED, error="transient_payload_expired")
        logger.warning("transient_email_payload_expired", extra={"email_log_id": log_id})
        return
    log = _claim_log(log_id)
    if log is None:
        return
    # In memory only: _deliver never re-saves the body fields, so the stored row stays redacted.
    log.to_email, log.subject = payload["to"], payload["subject"]
    log.text_body, log.html_body = payload["text"], payload["html"]
    log._timing_ineligible = True
    _deliver(log)
    log.refresh_from_db()
    if log.status == EmailLog.Status.FAILED:
        logger.warning("transient_email_failed", extra={"email_log_id": log_id, "attempt": self.request.retries})
        try:
            raise self.retry(countdown=_retry_countdown(self.request.retries))
        except self.MaxRetriesExceededError:
            return


@shared_task(bind=True, max_retries=3, soft_time_limit=email_task_soft_limit(), time_limit=email_task_hard_limit())
@guarded(sending=True)
def deliver_transient_sms_task(self, sealed):
    """Send one sealed SMS (login/verification code). A provider rejection retries with backoff; a send that
    already reported success is never repeated because the task returns before any retry."""
    from apps.integrations.sms import send_sms_now
    from apps.integrations.tasks import _retry_countdown
    from apps.integrations.transient_mail import unseal
    record_worker_heartbeat()
    payload = unseal(sealed)
    if payload is None:
        logger.warning("transient_sms_payload_expired")
        return
    outcome = send_sms_now(to=payload["to"], body=payload["body"])
    if outcome == "failed":
        try:
            raise self.retry(countdown=_retry_countdown(self.request.retries))
        except self.MaxRetriesExceededError:
            return
