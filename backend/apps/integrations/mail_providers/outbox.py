"""Free dispatch/drain hooks. I wires the shared enqueue/claim/retry seams."""

import time
from contextlib import contextmanager, nullcontext
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from apps.audit import services as audit
from .budget_config import free_profile
from .delivery import deadline, execution_guard


@contextmanager
def delivery_deadline(monotonic_deadline, *, guard=None):
    token = deadline.set(monotonic_deadline)
    guard_token = execution_guard.set(guard)
    try:
        yield
    finally:
        deadline.reset(token)
        execution_guard.reset(guard_token)


def enqueue_inline_allowed(*, sync=False, persist_body=True):
    """Gate both sync dispatch and .delay(); only transient proofs bypass a tick."""
    if not free_profile():
        return True
    return bool(sync and (not persist_body or deadline.get() is not None))


def claim_due(log, *, now=None):
    """Call inside existing locked _claim_log / manual-retry transaction."""
    if not free_profile():
        return True
    now = now or timezone.now()
    return log.email_retryable and (log.email_retry_at is None or log.email_retry_at <= now)


def defer_delivery(log, reason):
    from apps.integrations.models import EmailLog
    log.status = EmailLog.Status.PENDING
    log.error = reason.code
    # Unknown acceptance needs reconciliation, not a blind second provider call.
    log.email_retryable = reason.retry_at is not None or reason.code == "email_tick_budget_exhausted"
    log.email_retry_at = reason.retry_at or timezone.now() + timedelta(minutes=10)
    if getattr(log, "_timing_ineligible", False):
        # Short-lived redacted proofs never become tomorrow's notifications.
        log.status, log.email_retryable = EmailLog.Status.FAILED, False
    log.save(update_fields=["status", "error", "email_retry_at", "email_retryable", "updated_at"])
    audit.record(None, "email.budget_deferred", makerspace=log.makerspace, target=log,
                 meta={"reason": reason.code, "retryable": log.email_retryable})
    return log


def failed_delivery(log, exc):
    from .delivery import definite_nonacceptance
    code = getattr(exc, "status_code", None)
    # Configuration/auth failures require intervention; transient failures back off.
    permanent = definite_nonacceptance(exc) and code != 429
    log.email_retryable = not permanent and not getattr(log, "_timing_ineligible", False)
    log.email_retry_at = timezone.now() + timedelta(seconds=min(60 * 2 ** min(log.attempts, 8), 3600))


def drain(*, monotonic_deadline, limit=20, guard=None, cursor=0):
    """Bounded pending AND retry drain, reusing existing source/claim/PII gates.

    J passes its guard check callable; a lost guard stops before another claim/send.
    The caller owns recovery/source writer admission just like the existing task.
    """
    if not free_profile():
        return {"processed": 0, "reason": "full_profile"}
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("Invalid mail drain batch size.")
    if type(cursor) is not int or cursor < 0:
        raise ValueError("Invalid mail drain cursor.")
    from apps.integrations.models import EmailLog
    from apps.integrations.delivery_sources import has_retry_content
    from apps.integrations.tasks import _claim_log
    from apps.integrations.dispatch_delivery import _deliver
    from apps.integrations.smtp_validation import email_task_hard_limit, SENDING_CLAIM_STALE_BUFFER_SECONDS
    now = timezone.now()
    stale = now - timedelta(seconds=email_task_hard_limit() + SENDING_CLAIM_STALE_BUFFER_SECONDS)
    rows = EmailLog.objects.filter(email_retryable=True).filter(
        Q(status__in=[EmailLog.Status.PENDING, EmailLog.Status.FAILED]) |
        Q(status=EmailLog.Status.SENDING, updated_at__lte=stale)).filter(
        Q(email_retry_at__isnull=True) | Q(email_retry_at__lte=now))
    ids = list(rows.filter(pk__gt=cursor).order_by("pk").values_list("pk", flat=True)[:limit + 1])
    count, visited = 0, cursor
    with delivery_deadline(monotonic_deadline, guard=guard):
        for pk in ids[:limit]:
            if time.monotonic() + 2 >= monotonic_deadline:
                break
            if guard:
                guard()
            candidate = EmailLog.objects.filter(pk=pk).first()
            visited = pk  # J persists this cursor, including frozen/ineligible rows.
            if candidate is None:
                continue
            from apps.tenant_migration.gate_runtime import fanout_tenant_write
            custody = candidate.stream == "backup" and candidate.event in {
                "archive_custody_alarm", "tenant_exit_custody_alarm"}
            boundary = (fanout_tenant_write(candidate.makerspace_id,
                        operation="free_mail_drain", counts={})
                        if candidate.makerspace_id and not custody else nullcontext(True))
            with boundary as allowed:
                if not allowed:
                    continue
                if not has_retry_content(candidate):
                    _expire_redacted(candidate)
                    continue
                log = _claim_log(pk)
                if log is not None:
                    if guard:
                        guard()
                    _deliver(log)
                    count += 1
    remaining = bool(ids) and (visited < ids[-1] or len(ids) > limit)
    return {"processed": count, "remaining": remaining, "cursor": visited if remaining else 0}


def _expire_redacted(candidate):
    """An interrupted synchronous proof must never block the persistent backlog."""
    from django.db import transaction
    from apps.encryption.write_fence import assert_mapped_write_allowed
    from apps.integrations.models import EmailLog
    from apps.integrations.delivery_sources import has_retry_content
    with transaction.atomic():
        assert_mapped_write_allowed(candidate.makerspace_id)
        log = EmailLog.objects.select_for_update().get(pk=candidate.pk)
        if has_retry_content(log) or log.status in {EmailLog.Status.SENT, EmailLog.Status.SKIPPED}:
            return
        log.status, log.email_retryable = EmailLog.Status.FAILED, False
        log.error = "email_no_retry_content"
        log.save(update_fields=["status", "email_retryable", "error", "updated_at"])
        audit.record(None, "email.redacted_proof_expired", makerspace=log.makerspace, target=log)
