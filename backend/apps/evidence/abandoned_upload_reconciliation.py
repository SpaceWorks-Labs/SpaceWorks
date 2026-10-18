"""Mandatory late-write reconciliation of committed abandoned-upload receipts.

A presigned upload admitted just before URL expiry can finish after cleanup deleted the
row and both keys. Each receipt therefore re-deletes every version of its exact final
key and ``staging/<key>`` forever, on a bounded fair schedule: success moves the
receipt 360 minutes out, failure 720 minutes out (two sweeps), so a batch-sized set of
failing receipts can never starve the rest of the backlog.

This is deployment coordination, not tenant mutation: it touches only receipt
scheduling fields and receipt-named keys, never quota, audit or live evidence. It
runs regardless of the cleanup switches, tenant servability, source-gate state
(``MIGRATED_OUT``) or whether the source makerspace still exists. Non-``NORMAL``
deployment recovery is the only fence.
"""

from datetime import timedelta
import logging

from django.conf import settings
from django.utils import timezone

from apps.backup.models import DeploymentRecoveryState
from apps.evidence import storage
from apps.evidence.models import EvidenceAbandonedUploadReceipt
from apps.storage_capabilities import CapabilityError
from apps.storage_capabilities.budget import checkpoint, raise_if_fenced


logger = logging.getLogger(__name__)

SUCCESS_INTERVAL = timedelta(minutes=360)
FAILURE_BACKOFF = timedelta(minutes=720)


def receipt_backlog(now):
    receipts = EvidenceAbandonedUploadReceipt.objects.all()
    return {
        "receipts_total": receipts.count(),
        "receipts_due": receipts.filter(next_reconcile_at__lte=now).count(),
    }


def reconcile_receipts(*, dry_run=False, now=None, batch_size=None):
    now = now or timezone.now()
    summary = {
        **receipt_backlog(now),
        "receipts_reconciled": 0,
        "receipts_failed": 0,
        "has_more": False,
        "recovery_blocked": False,
    }
    if dry_run:
        summary["has_more"] = summary["receipts_due"] > 0
        return _logged(summary, dry_run=True)
    if not DeploymentRecoveryState.objects.filter(
        pk=1, mode=DeploymentRecoveryState.Mode.NORMAL
    ).exists():
        summary["recovery_blocked"] = True
        return _logged(summary, dry_run=False)
    configured = settings.EVIDENCE_RETENTION_BATCH_SIZE if batch_size is None else batch_size
    limit = min(max(int(configured), 1), 1000)
    if getattr(settings, "SPACEWORKS_DEPLOYMENT_PROFILE", "full") == "free":
        limit = min(limit, 5)
    due = list(
        EvidenceAbandonedUploadReceipt.objects.filter(next_reconcile_at__lte=now)
        .order_by("next_reconcile_at", "pk")
        .values_list("pk", "object_key")[: limit + 1]
    )
    summary["has_more"] = len(due) > limit
    for pk, object_key in due[:limit]:
        try:
            checkpoint()
        except CapabilityError as exc:
            if exc.code != "storage_budget_exhausted":
                raise
            summary.update(has_more=True, budget_deferred=True)
            break
        if _reconcile_receipt(pk, object_key, now=now):
            summary["receipts_reconciled"] += 1
        else:
            summary["receipts_failed"] += 1
    return _logged(summary, dry_run=False)


def _reconcile_receipt(pk, object_key, *, now):
    receipts = EvidenceAbandonedUploadReceipt.objects.filter(pk=pk)
    try:
        from apps.operations.cloud_quotas.receipt_storage import delete_receipt_keys
        delete_receipt_keys(receipts.get())
    except Exception as exc:  # per-receipt isolation; retried two sweeps later
        raise_if_fenced(exc)
        receipts.reconcile_update(
            next_reconcile_at=now + FAILURE_BACKOFF,
            last_error=getattr(exc, "code", type(exc).__name__)[:500],
        )
        logger.warning(
            "evidence_abandoned_receipt_reconcile_failed",
            extra={"receipt_id": pk, "error_type": type(exc).__name__},
        )
        return False
    checkpoint()
    receipts.reconcile_update(
        next_reconcile_at=now + SUCCESS_INTERVAL,
        last_reconciled_at=now,
        last_error="",
    )
    return True


def _logged(summary, *, dry_run):
    logger.info(
        "evidence_abandoned_receipt_reconciliation_completed",
        extra={"dry_run": dry_run, **summary},
    )
    return summary
