"""Bounded, idempotent expiry of evidence bytes; the evidence row is always retained.

Object expiry never deletes a row and never claims a row abandoned-upload cleanup owns
(`cleaning`); attached evidence metadata remains immutable.
"""

from dataclasses import dataclass
from datetime import timedelta
import logging
import uuid

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.backup.models import DeploymentRecoveryState
from apps.evidence import storage
from apps.evidence.models import (
    EvidenceObjectRetentionState,
    EvidencePhoto,
    EvidenceUploadFinalization,
)
from apps.evidence.retention_policy import object_candidates, preview_object_expiry
from apps.makerspaces import limits
from apps.makerspaces.servability import servable_queryset
from apps.tenant_migration.gate_runtime import fanout_tenant_write
from apps.storage_capabilities.chunks import FreeSweep
from apps.storage_capabilities.budget import checkpoint, raise_if_fenced


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExpiryClaim:
    evidence_id: int
    makerspace_id: int
    object_key: str
    token: uuid.UUID
    recorded_size: int


def sweep_evidence_retention(*, dry_run=False, now=None, batch_size=None, cursor=None):
    now = now or timezone.now()
    summary = {
        "makerspaces_scanned": 0,
        "makerspaces_skipped": 0,
        "photos_eligible": 0,
        "photos_claimed": 0,
        "photos_expired": 0,
        "photos_failed": 0,
        "bytes_removed": 0,
        "continuation_required": False,
    }
    if not settings.EVIDENCE_OBJECT_EXPIRY_ENABLED and not dry_run:
        return _logged_summary(summary, dry_run=dry_run, disabled=True)
    if not DeploymentRecoveryState.objects.filter(
        pk=1, mode=DeploymentRecoveryState.Mode.NORMAL
    ).exists():
        summary["makerspaces_skipped"] = servable_queryset().count()
        return _logged_summary(summary, dry_run=dry_run, recovery_blocked=True)

    run_id = uuid.uuid4()
    configured_batch_size = (
        settings.EVIDENCE_RETENTION_BATCH_SIZE if batch_size is None else batch_size
    )
    batch_size = min(max(int(configured_batch_size), 1), 1000)
    window = FreeSweep(summary, cursor)
    batch_size = window.batch_size(batch_size)
    gate_counts = {"skipped": 0}
    for makerspace in window.makerspaces(servable_queryset().order_by("pk")):
        summary["makerspaces_scanned"] += 1
        if dry_run:
            preview = preview_object_expiry(makerspace, limit=batch_size, as_of=now)
            summary["photos_eligible"] += preview["object_candidates"]
            summary["continuation_required"] |= preview["has_more"]
            continue
        with fanout_tenant_write(
            makerspace.pk,
            operation="evidence_object_expiry",
            counts=gate_counts,
        ) as should_process:
            if not should_process:
                window.skip(makerspace.pk)
                continue
            _sweep_makerspace(
                makerspace,
                now=now,
                run_id=run_id,
                batch_size=batch_size,
                summary=summary,
                window=window,
            )
    summary["makerspaces_skipped"] += gate_counts["skipped"]
    return _logged_summary(
        summary, dry_run=dry_run, batch_size=batch_size,
    )


def _logged_summary(summary, *, dry_run, **context):
    logger.info(
        "evidence_object_expiry_sweep_completed",
        extra={"dry_run": dry_run, **context, **summary},
    )
    return summary


def _sweep_makerspace(makerspace, *, now, run_id, batch_size, summary, window):
    queryset, policy_days, cutoff = object_candidates(makerspace, as_of=now)
    queryset = window.candidates(queryset, makerspace.pk)
    candidate_ids = list(queryset.values_list("pk", flat=True)[: batch_size + 1])
    summary["photos_eligible"] += min(len(candidate_ids), batch_size)
    if len(candidate_ids) > batch_size:
        summary["continuation_required"] = True
    for evidence_id in candidate_ids[:batch_size]:
        if not window.before_item(makerspace.pk, evidence_id):
            return
        claim = _claim(evidence_id, now=now)
        if claim is None:
            continue
        summary["photos_claimed"] += 1
        try:
            final_size = storage.object_size(claim.object_key)
            staged_key = storage.staging_key(claim.object_key)
            staged_size = storage.object_size(staged_key)
            outcomes = {
                "final": storage.delete_object_strict(claim.object_key,
                    **_accounting_receipt(claim.evidence_id, "final")),
                "staging": storage.delete_object_strict(staged_key,
                    **_accounting_receipt(claim.evidence_id, "staging")),
            }
            size = final_size or staged_size or claim.recorded_size
            checkpoint()
            removed = _complete(
                claim,
                size=size,
                policy_days=policy_days,
                cutoff=cutoff,
                outcomes=outcomes,
                run_id=run_id,
            )
            summary["photos_expired"] += int(removed is not None)
            summary["bytes_removed"] += removed or 0
            if removed is not None:
                logger.info(
                    "evidence_object_expired",
                    extra={
                        "evidence_id": claim.evidence_id,
                        "makerspace_id": claim.makerspace_id,
                        "final_outcome": outcomes["final"],
                        "staging_outcome": outcomes["staging"],
                        "expired_size_bytes": removed,
                    },
                )
        except Exception as exc:  # per-object isolation keeps the bounded sweep moving
            _release(claim, exc)
            raise_if_fenced(exc)
            summary["photos_failed"] += 1
            logger.warning(
                "evidence_object_expiry_failed",
                extra={
                    "evidence_id": claim.evidence_id,
                    "makerspace_id": claim.makerspace_id,
                    "error_type": type(exc).__name__,
                },
            )
    window.finish_page(makerspace.pk, candidate_ids[:batch_size], len(candidate_ids) > batch_size)


def _claim(evidence_id, *, now):
    stale_before = now - timedelta(
        seconds=max(settings.EVIDENCE_URL_TTL_SECONDS, 60)
    )
    with transaction.atomic():
        photo = EvidencePhoto.objects.select_for_update().get(pk=evidence_id)
        finalization = EvidenceUploadFinalization.objects.select_for_update().filter(
            evidence_id=evidence_id
        ).first()
        state, _ = EvidenceObjectRetentionState.objects.select_for_update().get_or_create(
            evidence_id=evidence_id
        )
        # Never steal a row abandoned-upload cleanup owns.
        if state.status in (
            EvidenceObjectRetentionState.Status.EXPIRED,
            EvidenceObjectRetentionState.Status.CLEANING,
        ):
            return None
        if state.claim_token and state.claimed_at and state.claimed_at > stale_before:
            return None
        if (
            finalization is not None
            and finalization.status == EvidenceUploadFinalization.Status.PROMOTING
            and finalization.updated_at > stale_before
        ):
            return None
        token = uuid.uuid4()
        state.status = EvidenceObjectRetentionState.Status.EXPIRING
        state.claim_token = token
        state.claimed_at = now
        state.last_error = ""
        state.save(
            update_fields=(
                "status", "claim_token", "claimed_at", "last_error", "updated_at",
            )
        )
        recorded_size = (
            getattr(finalization, "size_bytes", None) or photo.size_bytes or 0
        )
        return ExpiryClaim(
            photo.pk, photo.makerspace_id, photo.object_key, token, recorded_size
        )


def _accounting_receipt(evidence_id, part):
    if getattr(settings, "SPACEWORKS_DEPLOYMENT_PROFILE", "full") != "free":
        return {}
    return {"operation_key": f"evidence-expiry:{evidence_id}:{part}"}


def _complete(claim, *, size, policy_days, cutoff, outcomes, run_id):
    with transaction.atomic():
        photo = EvidencePhoto.objects.select_for_update().get(pk=claim.evidence_id)
        finalization = EvidenceUploadFinalization.objects.select_for_update().filter(
            evidence_id=claim.evidence_id
        ).first()
        state = EvidenceObjectRetentionState.objects.select_for_update().get(
            evidence_id=claim.evidence_id
        )
        if state.status != EvidenceObjectRetentionState.Status.EXPIRING:
            return None
        if state.claim_token != claim.token:
            return None
        expired_at = timezone.now()
        state.status = EvidenceObjectRetentionState.Status.EXPIRED
        state.claim_token = None
        state.claimed_at = None
        state.object_expired_at = expired_at
        state.expired_size_bytes = size
        state.last_error = ""
        state.save()
        quota_was_charged = (
            not storage.uses_put_uploads()
            or finalization is None
            or finalization.quota_charged
        )
        if quota_was_charged:
            limits.free_storage(photo.makerspace, size)
        audit.record(
            None,
            "evidence.object_expired",
            makerspace=photo.makerspace,
            target=photo,
            meta={
                "policy_days": policy_days,
                "cutoff": cutoff.isoformat(),
                "final_outcome": outcomes["final"],
                "staging_outcome": outcomes["staging"],
                "expired_size_bytes": size,
                "sweep_run_id": str(run_id),
            },
        )
        return size


def _release(claim, exc):
    with transaction.atomic():
        EvidencePhoto.objects.select_for_update().filter(pk=claim.evidence_id).first()
        EvidenceUploadFinalization.objects.select_for_update().filter(
            evidence_id=claim.evidence_id
        ).first()
        state = EvidenceObjectRetentionState.objects.select_for_update().filter(
            evidence_id=claim.evidence_id,
            claim_token=claim.token,
            status=EvidenceObjectRetentionState.Status.EXPIRING,
        ).first()
        if state is None:
            return
        state.claim_token = None
        state.claimed_at = None
        state.last_error = getattr(exc, "code", type(exc).__name__)[:500]
        state.save(update_fields=("claim_token", "claimed_at", "last_error", "updated_at"))
