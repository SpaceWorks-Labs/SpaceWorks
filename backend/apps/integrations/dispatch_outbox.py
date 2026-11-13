from django.utils.translation import gettext
import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.integrations.models import DailyEmailCounter, EmailLog
from apps.integrations.smtp_validation import sanitize_email_error
from apps.makerspaces import domain_verification, limits
from .dispatch_policy import email_module_blocks

logger = logging.getLogger(__name__)

def _create_email_log(**values):
    """Hold the shared fence across the mapped EmailLog insert."""
    from apps.encryption.write_fence import assert_mapped_write_allowed

    with transaction.atomic():
        makerspace = values.get("makerspace")
        assert_mapped_write_allowed(None if makerspace is None else makerspace.id)
        return EmailLog.objects.create(**values)


def _create_platform_counted(makerspace, values):
    """Create a platform-path email row, reserving the month's allowance (decision 281).

    The row is stamped ``provider_source="platform"`` AT ENQUEUE, so queued-but-undelivered mail counts
    toward the limit and a burst cannot overshoot it. The space row lock serialises the check and the
    insert; a skipped or failed row stops counting, which releases the reservation.
    """
    from apps.managed_hosting import platform_limits
    with transaction.atomic():
        type(makerspace).objects.select_for_update(no_key=True).get(pk=makerspace.pk)
        refusal = platform_limits.channel_refusal(makerspace, "email")
        if refusal:
            return _create_email_log(**values, status=EmailLog.Status.SKIPPED, error=refusal)
        return _create_email_log(**values, provider_source="platform")


def dispatch_email(
    *,
    to_email,
    subject,
    text_body,
    html_body="",
    makerspace=None,
    stream="",
    event="",
    audience="",
    connection="makerspace",
    persist_body=True,
    sync=False,
    recipient_id=None,
    feature="",
    source_kind="",
    source_id=None,
    source_metadata=None,
):
    from apps.integrations.dispatch import _deliver

    platform_minimized = settings.PII_ENCRYPTION_ENABLED and makerspace is None
    if platform_minimized:
        # Keyless platform mail is deliberately transient: it cannot be queued or retried.
        sync = True
        persist_body = False
        stream, event, audience = "platform", "platform_email", "system"
    if not persist_body and not sync:
        raise ValueError("persist_body=False requires sync=True")

    from apps.integrations.email_preferences import blocked_reason
    reason = blocked_reason(makerspace, to_email, user_id=recipient_id,
                            feature=feature, stream=stream, event=event)
    if reason or email_module_blocks(makerspace, stream, event):
        # Recorded rather than dropped: the operator needs to see what their toggle
        # suppressed. The body is stored only when the caller allowed persistence --
        # a skipped row must not become the place a redacted body leaks into.
        return _create_email_log(
            makerspace=makerspace,
            to_email="" if platform_minimized else to_email,
            subject=gettext("Platform email") if platform_minimized else subject,
            text_body=text_body if persist_body else "",
            html_body=html_body if persist_body else "",
            stream=stream,
            event=event,
            audience=audience,
            connection_kind=connection,
            recipient_id=recipient_id,
            feature=feature,
            source_kind=source_kind, source_id=source_id, source_metadata=source_metadata or {},
            status=EmailLog.Status.SKIPPED,
            error=reason or "Email is disabled for this makerspace.",
        )

    platform_path = False
    if makerspace is not None and connection == "makerspace":
        # Decisions 240/281: a space without its own mail account uses the platform's ONLY while its
        # Space Manager allows it; the monthly allowance is reserved below, when the row is created.
        from apps.managed_hosting import platform_limits
        from apps.managed_hosting.platform_switch import platform_allowed
        platform_path = not platform_limits.uses_own_email(makerspace)
        if platform_path and not platform_allowed(makerspace, "email"):
            return _create_email_log(
                makerspace=makerspace, to_email=to_email, subject=subject,
                text_body=text_body if persist_body else "", html_body=html_body if persist_body else "",
                stream=stream, event=event, audience=audience, connection_kind=connection,
                recipient_id=recipient_id, feature=feature, source_kind=source_kind, source_id=source_id,
                source_metadata=source_metadata or {}, status=EmailLog.Status.SKIPPED,
                error="platform_email_disabled",
            )
    if (
        domain_verification.hosts_other_spaces()
        and makerspace is not None
        and connection == "makerspace"
    ):
        # Imported BEFORE the try: `except PiiWriteFenced` below names it, and a failure
        # raised ahead of an in-try import (the quota lookup itself) would otherwise turn
        # the intended logged fail-open into UnboundLocalError out of the mail path.
        from apps.encryption.write_fence import (
            PiiWriteFenced,
            assert_mapped_write_allowed,
        )

        try:
            limit = limits.resource_limit(makerspace, "email")
            if limit is not None:
                with transaction.atomic():
                    assert_mapped_write_allowed(makerspace.id)
                    counter, _ = DailyEmailCounter.objects.get_or_create(
                        makerspace=makerspace,
                        day=timezone.now().date(),
                    )
                    counter = DailyEmailCounter.objects.select_for_update().get(
                        pk=counter.pk
                    )
                    if counter.count >= limit:
                        return EmailLog.objects.create(
                            makerspace=makerspace,
                            to_email=to_email,
                            subject=subject,
                            text_body=text_body if persist_body else "",
                            html_body=html_body if persist_body else "",
                            stream=stream,
                            event=event,
                            audience=audience,
                            connection_kind=connection,
                            recipient_id=recipient_id,
                            feature=feature,
                            source_kind=source_kind, source_id=source_id, source_metadata=source_metadata or {},
                            status=EmailLog.Status.FAILED,
                            error="Daily email limit reached for this space.",
                        )
                    counter.count = counter.count + 1
                    counter.save(update_fields=["count"])
        except PiiWriteFenced:
            raise
        except Exception:
            logger.exception(
                "daily_email_limit_check_failed",
                extra={"makerspace_id": makerspace.pk},
            )
        from apps.managed_hosting.enforcement import monthly_refusal
        refusal = monthly_refusal(makerspace, "email_monthly")  # #187A; None with plans off
        if refusal:
            return _create_email_log(
                makerspace=makerspace, to_email=to_email, subject=subject,
                text_body=text_body if persist_body else "", html_body=html_body if persist_body else "",
                stream=stream, event=event, audience=audience, connection_kind=connection,
                recipient_id=recipient_id, feature=feature, source_kind=source_kind, source_id=source_id,
                source_metadata=source_metadata or {}, status=EmailLog.Status.FAILED, error=refusal,
            )

    # persist_body=False keeps the rendered body OUT of the stored row (e.g. password
    # reset emails embed a live recovery token in the body - persisting it would leave a
    # usable token in the DB + Django admin until expiry). We still deliver the real body:
    # it's set on the in-memory instance below and _deliver never re-saves the body fields.
    log_values = dict(
        makerspace=makerspace,
        to_email="" if platform_minimized else to_email,
        subject=gettext("Platform email") if platform_minimized else subject,
        text_body=text_body if persist_body else "",
        html_body=html_body if persist_body else "",
        stream=stream,
        event=event,
        audience=audience,
        connection_kind=connection,
        recipient_id=recipient_id,
        feature=feature,
        source_kind=source_kind, source_id=source_id, source_metadata=source_metadata or {},
    )
    log = _create_platform_counted(makerspace, log_values) if platform_path else _create_email_log(**log_values)
    if not persist_body:
        # In-memory only - _deliver's save(update_fields=...) excludes the body fields,
        # so the stored row stays redacted while delivery uses the real content.
        log.text_body = text_body
        log.html_body = html_body
        log._timing_ineligible = True
    if platform_minimized:
        log.to_email = to_email
        log.subject = subject
    if persist_body and makerspace is not None:
        from apps.integrations.timing_dispatch import defer_log
        if defer_log(log, kind='email'):
            return log
    from .mail_providers.outbox import enqueue_inline_allowed
    if not enqueue_inline_allowed(sync=sync, persist_body=persist_body):
        return log
    if sync:
        if not persist_body:
            # Secret-bearing mail leaves the request cycle too: sealed payload -> Celery worker (transient_mail).
            from .transient_mail import queue_email
            if queue_email(log, to_email=to_email, subject=subject, text_body=text_body, html_body=html_body):
                return log
        return _deliver(log)
    transaction.on_commit(lambda lid=log.id: _enqueue(lid))
    return log


def _enqueue(log_id):
    from .mail_providers.outbox import enqueue_inline_allowed
    if not enqueue_inline_allowed():
        return
    from apps.integrations.tasks import deliver_email_task

    try:
        deliver_email_task.delay(log_id)
    except Exception as exc:
        from apps.encryption.write_fence import assert_mapped_write_allowed

        with transaction.atomic():
            candidate = EmailLog.objects.only("makerspace_id").filter(pk=log_id).first()
            if candidate is not None:
                assert_mapped_write_allowed(candidate.makerspace_id)
                log = EmailLog.objects.select_for_update().get(pk=log_id)
                log.status = EmailLog.Status.FAILED
                log.error = sanitize_email_error(exc)
                log.save(update_fields=["status", "error", "updated_at"])
        logger.error(
            "email_enqueue_failed",
            extra={"email_log_id": log_id, "error_class": type(exc).__name__},
        )
