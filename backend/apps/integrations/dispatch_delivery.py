from apps.integrations.notification_cutover import guarded, sending_allowed
import logging

from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.utils import timezone

from apps.integrations.models import EmailLog
from apps.integrations.smtp_validation import sanitize_email_error
from .dispatch_policy import email_module_blocks

logger = logging.getLogger(__name__)

@guarded()
def _deliver(log):
    if not sending_allowed():
        return log
    if log.status in {EmailLog.Status.SENT, EmailLog.Status.SKIPPED}:
        from .delivery_sources import finished
        finished(log)
        return log

    # Custody alarms are deployment control-plane mail even when addressed to a
    # tenant custodian. Keep the source-gate exemption as narrow as the task policy.
    custody_alarm = log.stream == "backup" and log.event in {
        "archive_custody_alarm", "tenant_exit_custody_alarm",
    }
    if log.makerspace_id and not custody_alarm:
        from apps.tenant_migration.gate_runtime import assert_write_allowed
        from apps.encryption.write_fence import assert_mapped_write_allowed
        # Reuse the task's dedicated boundary lock before opening an application
        # transaction; a second connection can queue behind migration's writer.
        assert_write_allowed(log.makerspace_id)
        with transaction.atomic():
            assert_mapped_write_allowed(log.makerspace_id)

    from .delivery_sources import prepare, finished
    from .delivery_content import content, recipient_address
    if not prepare(log):
        log.status, log.error = EmailLog.Status.SKIPPED, 'delivery_source_no_longer_eligible'
        log.save(update_fields=['status', 'error', 'updated_at'])
        finished(log)
        return log

    if log.event == 'daily_digest':
        from apps.integrations.reminders_deferred import _allowed
        if not _allowed(log, log.makerspace):
            log.status, log.error = EmailLog.Status.SKIPPED, 'notification_disabled_before_release'
            log.save(update_fields=['status', 'error', 'updated_at'])
            finished(log)
            return log

    from apps.encryption.write_fence import assert_mapped_write_allowed

    with transaction.atomic():
        assert_mapped_write_allowed(log.makerspace_id)

    # Re-checked at delivery, not just at dispatch: a queued row can sit in Celery
    # across a module uninstall, and the retry path re-enters here too. Gating only
    # `dispatch_email` would let everything already in flight through.
    from apps.integrations.email_preferences import blocked_reason, unsubscribe_headers
    reason = blocked_reason(log.makerspace, recipient_address(log), user_id=log.recipient_id,
                            feature=log.feature, stream=log.stream, event=log.event)
    if reason or email_module_blocks(log.makerspace, log.stream, log.event):
        log.status = EmailLog.Status.SKIPPED
        log.error = reason or "Email is disabled for this makerspace."
        log.save(update_fields=["status", "error", "updated_at"])
        finished(log)
        return log

    from apps.integrations.timing_dispatch import defer_log
    try:
        from .mail_providers.delivery import delivery_timeout
        from .mail_providers.budget_config import free_profile
        if defer_log(log, kind='email'):
            return log
    except Exception as exc:
        log.status, log.error = EmailLog.Status.FAILED, 'delivery_timing_unavailable'
        log.attempts += 1
        log.save(update_fields=['status', 'error', 'attempts', 'updated_at'])
        finished(log)
        logger.error('source_delivery_timing_failed', extra={'email_log_id': log.pk, 'error_class': type(exc).__name__})
        return log

    deferred = False
    try:
        from apps.integrations.email import (
            makerspace_mail_connection,
            platform_mail_connection,
        )

        if log.connection_kind == "makerspace" and log.makerspace_id:
            connection, from_email = makerspace_mail_connection(log.makerspace)
        else:
            connection, from_email = platform_mail_connection()
        log.provider_source = "platform" if connection is None else getattr(connection, "provider_source", "")
        if free_profile():
            # Connection creation does no remote I/O. Bound the selected transport
            # before the provider is called; full paths retain their old timeout.
            seconds = delivery_timeout()
            if hasattr(connection, "mail_timeout"):
                connection.mail_timeout = seconds
            elif connection is not None:
                connection.timeout = seconds / 2
        rendered = content(log)
        msg = EmailMultiAlternatives(
            subject=rendered.subject,
            body=rendered.text_body,
            from_email=from_email,
            to=[rendered.to_email],
            connection=connection,
            headers=unsubscribe_headers(log),
        )
        if rendered.html_body:
            msg.attach_alternative(rendered.html_body, "text/html")
        if rendered.attachments:
            from apps.payments.document_delivery import render_attachment
            for reference in rendered.attachments:
                msg.attach(*render_attachment(reference, makerspace_id=log.makerspace_id,
                                              recipient_id=log.recipient_id))
        from .mail_providers.delivery import send
        send(log, msg)  # raises unless the transport accepted the message
        # Provider backends may expose an accepted-message ID; SMTP itself does not.
        message_id = getattr(msg, "provider_message_id", "") or getattr(msg, "spaceworks_provider_message_id", "")
        if not message_id:
            message_id = getattr(getattr(msg, "anymail_status", None), "message_id", "")
        if isinstance(message_id, str) and len(message_id) <= 255:
            log.provider_message_id = message_id
    except Exception as exc:
        from .mail_providers.budget import BudgetDeferred
        if isinstance(exc, BudgetDeferred):
            from .mail_providers.outbox import defer_delivery
            deferred = True
            return defer_delivery(log, exc)
        from apps.payments.document_delivery import DocumentDeliveryError
        log.status = EmailLog.Status.FAILED
        log.error = str(exc) if isinstance(exc, DocumentDeliveryError) else sanitize_email_error(exc)
        if free_profile():
            from .mail_providers.outbox import failed_delivery
            failed_delivery(log, exc)
        logger.error(
            "email_delivery_failed",
            extra={"email_log_id": log.pk, "error_class": type(exc).__name__},
        )
        # Heads-up in the staff inbox on FIRST failure only (attempts is bumped in
        # `finally` below, so 0 here means the initial delivery attempt) — avoids a
        # row per retry. Fully fail-safe; never affects delivery.
        if log.attempts == 0 and log.makerspace_id:
            from apps.notifications.emit import emit_notification
            from apps.operations.notifications_p2_alerts import email_failure_intent

            emit_notification(
                log.makerspace,
                level="warning",
                event="email.failed",
                source_intent=email_failure_intent(log),
                title="Email delivery failed",
                body=f"Email log #{log.pk} delivery failed.",
            )
    else:
        log.status = EmailLog.Status.SENT
        log.error = ""
        log.sent_at = timezone.now()
        log.email_retry_at = None
        config = getattr(connection, "spaceworks_mail_config", None)
        log.provider_name = config.provider if config else ""
        if not log.provider_message_id:
            provider_id = getattr(msg, "spaceworks_provider_message_id", "")
            if not provider_id:
                provider_id = getattr(getattr(msg, "anymail_status", None), "message_id", "")
            log.provider_message_id = provider_id[:200] if isinstance(provider_id, str) else ""
        if log.makerspace_id:
            from .email_preferences import address_hash
            log.provider_recipient_hash = address_hash(log.makerspace_id, rendered.to_email)
    finally:
        if not deferred:
            log.attempts += 1
        log.save(
            update_fields=[
                "provider_source",
                "provider_message_id",
                "status",
                "error",
                "attempts",
                "sent_at",
                "updated_at",
                "email_retry_at", "email_retryable", "provider_name",
                "provider_recipient_hash",
            ]
        )
    finished(log)
    return log
