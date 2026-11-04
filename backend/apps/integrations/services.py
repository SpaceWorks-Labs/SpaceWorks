from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit
from apps.integrations.delivery_sources import has_retry_content, retry
from apps.integrations.dispatch import _enqueue
from apps.integrations.models import EmailLog
from apps.integrations.smtp_validation import sending_claim_is_stale


class EmailRetryError(Exception):
    pass


def retry_email_log(actor, log):
    # Failed sends are always retriable. A SENDING row is normally an in-flight claim
    # (must NOT be retried — that would double-deliver), but a STALE claim means the
    # worker died after claiming and before committing the result, leaving it stuck
    # forever — surface that in the Retry path so it stays recoverable without a DB fix.
    from apps.encryption.write_fence import assert_mapped_write_allowed

    with transaction.atomic():
        from apps.tenant_migration.gate_runtime import _boundary_shared_locks, assert_write_allowed
        if log.makerspace_id and log.makerspace_id not in _boundary_shared_locks.get():
            assert_write_allowed(log.makerspace_id)
        assert_mapped_write_allowed(log.makerspace_id)
        locked = EmailLog.objects.select_for_update().get(pk=log.pk)
        from .mail_providers.outbox import claim_due
        from .mail_retry_policy import unresolved_acceptance, rearm_rejected_configuration
        if unresolved_acceptance(locked) or (not claim_due(locked) and not rearm_rejected_configuration(locked)):
            raise EmailRetryError("Delivery is deferred or requires acceptance reconciliation.")
        if locked.status == EmailLog.Status.SENDING and not sending_claim_is_stale(locked):
            raise EmailRetryError("This email is still sending; only stalled sends can be retried.")
        if locked.status not in (EmailLog.Status.FAILED, EmailLog.Status.SENDING):
            raise EmailRetryError("Only failed or stalled emails can be retried.")
        if not has_retry_content(locked):
            raise EmailRetryError("This email cannot be retried (no stored content).")
        try:
            retry(locked, actor)
        except ValidationError as exc:
            raise EmailRetryError(str(exc.detail)) from exc
        locked.status = EmailLog.Status.PENDING
        locked.error = ""
        locked.save(update_fields=["status", "error", "updated_at"])
        audit.record(
            actor,
            "email.retried",
            makerspace=locked.makerspace,
            target=locked,
            meta={"email_log_id": locked.pk, "event": locked.event, "stream": locked.stream},
        )
        transaction.on_commit(lambda: _enqueue(locked.pk))
        return locked
