"""Two-stage, bounded, idempotent cleanup of abandoned (never-consumed) evidence uploads.

Only a post-migration presign proven ``unconsumed`` with no relationship, no
consumption audit and no live coordination claim can be removed; attached evidence is
never touched. Per tenant: source-gate fan-out boundary, then the report retention
fence (the first durable operation), then candidates strictly below both the age
cutoff and the fenced watermark. Object deletion runs outside the database between a
``cleaning`` claim and one final transaction that settles quota once, writes the
permanent receipt, deletes the sidecars and the photo, and appends one audit row.
"""

import logging
import uuid

from django.conf import settings
from django.utils import timezone

from apps.backup.models import DeploymentRecoveryState
from apps.evidence import storage
from apps.evidence.abandoned_upload_candidates import (
    InvalidAbandonedPolicy,
    abandoned_policy,
    abandoned_queryset,
    minimum_age,
)
from apps.evidence.abandoned_upload_state import claim, complete, release
from apps.evidence.models import EvidenceRetentionPolicy
from apps.makerspaces.servability import servable_queryset
from apps.operations.report_rollups import REFINALIZE_LOOKBACK, satisfy_retention_fence
from apps.tenant_migration.gate_runtime import fanout_tenant_write
from apps.storage_capabilities.chunks import FreeSweep
from apps.storage_capabilities.budget import checkpoint, raise_if_fenced


logger = logging.getLogger(__name__)


def _summary():
    return {
        "makerspaces_scanned": 0,
        "makerspaces_skipped": 0,
        "photos_eligible": 0,
        "photos_claimed": 0,
        "photos_deleted": 0,
        "photos_failed": 0,
        "bytes_removed": 0,
        "quota_released_bytes": 0,
        "continuation_required": False,
    }


def _batch(batch_size):
    configured = settings.EVIDENCE_RETENTION_BATCH_SIZE if batch_size is None else batch_size
    return min(max(int(configured), 1), 1000)


def opted_in_makerspaces():
    ids = EvidenceRetentionPolicy.objects.filter(
        abandoned_upload_cleanup_enabled=True
    ).values_list("makerspace_id", flat=True)
    return servable_queryset().filter(pk__in=ids).order_by("pk")


def sweep_abandoned_evidence_uploads(*, dry_run=False, now=None, batch_size=None, cursor=None):
    now = now or timezone.now()
    summary = _summary()
    if not settings.EVIDENCE_ABANDONED_UPLOAD_CLEANUP_ENABLED and not dry_run:
        return _logged(summary, dry_run=dry_run, disabled=True)
    if not DeploymentRecoveryState.objects.filter(
        pk=1, mode=DeploymentRecoveryState.Mode.NORMAL
    ).exists():
        summary["makerspaces_skipped"] = opted_in_makerspaces().count()
        return _logged(summary, dry_run=dry_run, recovery_blocked=True)
    batch_size = _batch(batch_size)
    window = FreeSweep(summary, cursor)
    batch_size = window.batch_size(batch_size)
    run_id = uuid.uuid4()
    gate_counts = {"skipped": 0}
    for makerspace in window.makerspaces(opted_in_makerspaces()):
        summary["makerspaces_scanned"] += 1
        if dry_run:
            _preview(makerspace, now=now, batch_size=batch_size, summary=summary)
            continue
        with fanout_tenant_write(
            makerspace.pk,
            operation="evidence_abandoned_upload_cleanup",
            counts=gate_counts,
        ) as should_process:
            if not should_process:
                window.skip(makerspace.pk)
                continue
            _sweep_makerspace(
                makerspace, now=now, run_id=run_id, batch_size=batch_size, summary=summary,
                window=window,
            )
    summary["makerspaces_skipped"] += gate_counts["skipped"]
    return _logged(summary, dry_run=dry_run, batch_size=batch_size)


def _logged(summary, *, dry_run, **context):
    logger.info(
        "evidence_abandoned_upload_cleanup_completed",
        extra={"dry_run": dry_run, **context, **summary},
    )
    return summary


def _age_cutoff(makerspace, now):
    days = abandoned_policy(makerspace.pk)[3]
    return days, now - minimum_age(days)


def _preview(makerspace, *, now, batch_size, summary):
    """Dry-run: no fence, lock, storage call, quota, audit or deletion."""
    try:
        _days, cutoff = _age_cutoff(makerspace, now)
    except InvalidAbandonedPolicy:
        return
    ids = list(abandoned_queryset(makerspace.pk, cutoff).values_list("pk", flat=True)[: batch_size + 1])
    summary["photos_eligible"] += min(len(ids), batch_size)
    summary["continuation_required"] |= len(ids) > batch_size


def _sweep_makerspace(makerspace, *, now, run_id, batch_size, summary, window):
    try:
        days, age_cutoff = _age_cutoff(makerspace, now)
    except InvalidAbandonedPolicy:
        window.skip(makerspace.pk)
        logger.warning(
            "evidence_abandoned_upload_policy_invalid",
            extra={"makerspace_id": makerspace.pk},
        )
        return
    # The fence is the first durable per-tenant operation. Rolled buckets are re-derived
    # for REFINALIZE_LOOKBACK below the watermark, so stay below that window too.
    try:
        cursor = satisfy_retention_fence(makerspace, now, actor=None)
    except Exception:  # an unfenced tenant is skipped; nothing durable happened yet
        window.skip(makerspace.pk)
        summary["makerspaces_skipped"] += 1
        logger.warning(
            "evidence_abandoned_upload_fence_failed",
            extra={"makerspace_id": makerspace.pk},
        )
        return
    cutoff = min(age_cutoff, cursor.rolled_through - REFINALIZE_LOOKBACK)
    queryset = window.candidates(abandoned_queryset(makerspace.pk, cutoff), makerspace.pk)
    ids = list(queryset.values_list("pk", flat=True)[: batch_size + 1])
    summary["photos_eligible"] += min(len(ids), batch_size)
    summary["continuation_required"] |= len(ids) > batch_size
    for evidence_id in ids[:batch_size]:
        if not window.before_item(makerspace.pk, evidence_id):
            return
        current = claim(evidence_id, makerspace_id=makerspace.pk, cutoff=cutoff, now=now)
        if current is None:
            continue
        summary["photos_claimed"] += 1
        try:
            staged_key = storage.staging_key(current.object_key)
            sizes = {
                "final": storage.object_size(current.object_key),
                "staging": storage.object_size(staged_key),
            }
            outcomes = {
                "final": storage.delete_object_strict(current.object_key,
                    **_accounting_receipt(current.evidence_id, "final")),
                "staging": storage.delete_object_strict(staged_key,
                    **_accounting_receipt(current.evidence_id, "staging")),
            }
            checkpoint()
            result = complete(
                current, cutoff=cutoff, policy_days=days, sizes=sizes,
                outcomes=outcomes, run_id=run_id,
            )
        except Exception as exc:  # per-photo isolation keeps the bounded sweep moving
            release(current, exc)
            raise_if_fenced(exc)
            summary["photos_failed"] += 1
            logger.warning(
                "evidence_abandoned_upload_cleanup_failed",
                extra={
                    "evidence_id": current.evidence_id,
                    "makerspace_id": makerspace.pk,
                    "error_type": type(exc).__name__,
                },
            )
            continue
        if result is None:
            continue
        summary["photos_deleted"] += 1
        summary["bytes_removed"] += result["removed_size_bytes"]
        summary["quota_released_bytes"] += result["quota_released_bytes"]
    window.finish_page(makerspace.pk, ids[:batch_size], len(ids) > batch_size)


def _accounting_receipt(evidence_id, part):
    if getattr(settings, "SPACEWORKS_DEPLOYMENT_PROFILE", "full") != "free":
        return {}
    return {"operation_key": f"evidence-abandoned:{evidence_id}:{part}"}
