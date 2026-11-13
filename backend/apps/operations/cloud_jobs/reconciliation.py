"""Reopen only a proven-drained outbox attempt after domain reconciliation."""
import re
from uuid import UUID

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.audit.services import record
from .tick_locks import task_guard

KEY = "notification-contract-outbox"


def reconcile_outbox(actor, token, evidence_sha256):
    from apps.operations.cloud_quotas.operator import require_operator
    actor = require_operator(actor)
    if (settings.SPACEWORKS_DEPLOYMENT_MODE != "managed" or
            settings.SPACEWORKS_DEPLOYMENT_PROFILE != "free"):
        raise ValueError("free_managed_profile_required")
    if not isinstance(evidence_sha256, str) or re.fullmatch("[0-9a-f]{64}", evidence_sha256) is None:
        raise ValueError("reconciliation_evidence_digest_invalid")
    attempt = UUID(str(token))
    from apps.backup.cloud_continuity import current_operation
    from apps.backup.managed.models import ManagedCaptureState
    from apps.backup.managed.writers import assert_capture_drained
    operation = current_operation()
    if operation is None:
        raise ValueError("retained_operation_guard_required")
    capture = ManagedCaptureState.objects.get(pk=1)
    if capture.paused_by is None:
        raise ValueError("managed_writer_drain_required")
    assert_capture_drained(capture.paused_by, operation)
    with task_guard(KEY, 10) as guard:
        if guard is None:
            raise ValueError("outbox_task_still_active")
        with transaction.atomic():
            from apps.operations.models import CloudTaskState
            state = CloudTaskState.objects.select_for_update().get(key=KEY)
            if state.status != "uncertain" or state.token != attempt:
                raise ValueError("outbox_attempt_identity_mismatch")
            guard.check()
            assert_capture_drained(capture.paused_by, operation)
            _require_domain_reconciled()
            state.status, state.failure_code, state.checkpoint = "deferred", "", {}
            state.next_due_at = timezone.now()
            state.save(update_fields=["status", "failure_code", "checkpoint", "next_due_at"])
            record(actor, "cloud.task_reconciled", meta={"task_key": KEY,
                "generation": state.generation, "attempt_token": str(attempt),
                "evidence_sha256": evidence_sha256})
            guard.check()
            assert_capture_drained(capture.paused_by, operation)
    return KEY


def _require_domain_reconciled():
    from apps.operations.models import CloudEmailReservation
    from apps.integrations.models import EmailLog, NotificationDeliveryLog
    from apps.integrations.models_contract import NotificationDelivery, NotificationEnvelope
    if CloudEmailReservation.objects.filter(state__in=("reserved", "uncertain")).exists():
        raise ValueError("mail_acceptance_reconciliation_required")
    if EmailLog.objects.filter(status="sending").exists():
        raise ValueError("mail_send_claim_reconciliation_required")
    if NotificationDelivery.objects.filter(claim_until__isnull=False).exists():
        raise ValueError("personal_delivery_claim_reconciliation_required")
    if NotificationDelivery.objects.filter(ambiguous_count__gt=0).exclude(
            state__in=("accepted", "sent", "delivered", "read", "skipped")).exists():
        raise ValueError("personal_delivery_acceptance_reconciliation_required")
    if NotificationDeliveryLog.objects.filter(status="sending").exists() or NotificationDeliveryLog.objects.filter(
            status="failed", attempts__gt=0, error__startswith="notification_delivery_failed").exists():
        raise ValueError("legacy_channel_acceptance_reconciliation_required")
    if NotificationEnvelope.objects.filter(source_kind="legacy.lifecycle", processed_at=None,
            context__free_fanout_state__in=("started", "uncertain")).exists():
        raise ValueError("legacy_fanout_reconciliation_required")
