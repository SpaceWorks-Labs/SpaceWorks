"""Exactly-once promotion of client-writable evidence staging objects."""

from datetime import timedelta
import time
import uuid

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.evidence.models import EvidencePhoto, EvidenceUploadFinalization


FINALIZATION_WAIT_SECONDS = 5
FINALIZATION_POLL_SECONDS = 0.05


class FinalizationInProgress(Exception):
    pass


def finalize_upload(evidence, max_bytes):
    """Validate and promote one staged upload without locking across S3 calls."""
    from apps.evidence import storage

    from apps.makerspaces.models_storage_reservations import StorageQuotaReservation
    reserved = StorageQuotaReservation.objects.filter(object_key=evidence.object_key).first()
    if reserved is not None:
        max_bytes = min(max_bytes, reserved.size_bytes)
    claim_token, completed = _claim(evidence.pk)
    if completed is not None:
        storage.delete_object(storage.staging_key(evidence.object_key))
        return completed
    if claim_token is None:
        recovered = _recover_or_wait(evidence, max_bytes)
        storage.delete_object(storage.staging_key(evidence.object_key))
        return recovered

    try:
        existing = _validated_or_none(storage, evidence.object_key, max_bytes)
        if existing is not None:
            result = existing
        else:
            staged_key = storage.staging_key(evidence.object_key)
            staged = _validated_or_none(storage, staged_key, max_bytes)
            if staged is None:
                _release_claim(evidence.pk, claim_token)
                return None
            storage.copy_object(staged_key, evidence.object_key)
            try:
                result = _validated_or_none(storage, evidence.object_key, max_bytes)
            except storage.EvidenceObjectValidationError:
                storage.delete_object(evidence.object_key)
                raise
            if result is None:
                raise storage.StorageUnavailable("Final evidence object was not created.")
        storage.delete_object(storage.staging_key(evidence.object_key))
        return _complete(evidence.pk, result)
    except Exception:
        _release_claim(evidence.pk, claim_token)
        raise


def charge_storage_once(evidence, size):
    """Charge finalized evidence once for either upload transport at the workflow boundary."""
    from apps.makerspaces.limits import charge_upload
    from apps.makerspaces.models import Makerspace

    with transaction.atomic():
        Makerspace.objects.select_for_update(no_key=True).get(pk=evidence.makerspace_id)
        # Older and POST-backed evidence can reach this boundary with validated
        # bytes but no sidecar. Lock the immutable identity before creating it,
        # matching promotion/retention lock order and serializing first charges.
        EvidencePhoto.objects.select_for_update().get(pk=evidence.pk)
        state, _ = EvidenceUploadFinalization.objects.select_for_update().get_or_create(
            evidence_id=evidence.pk,
            defaults={"status": EvidenceUploadFinalization.Status.FINALIZED,
                      "size_bytes": size, "content_type": evidence.content_type},
        )
        if state.quota_charged:
            return
        charge_upload(evidence.makerspace, size, kind="evidence", object_key=evidence.object_key)  # decision 284: split evidence byte limit
        state.quota_charged = True
        state.status = EvidenceUploadFinalization.Status.FINALIZED
        state.size_bytes = size
        state.content_type = state.content_type or evidence.content_type
        state.claim_token = None
        state.save(update_fields=["quota_charged", "status", "size_bytes", "content_type", "claim_token", "updated_at"])


def _claim(evidence_id):
    """Claim promotion while briefly locking the evidence row (immutable identity/content)."""
    with transaction.atomic():
        EvidencePhoto.objects.select_for_update().get(pk=evidence_id)
        state, _ = EvidenceUploadFinalization.objects.select_for_update().get_or_create(
            evidence_id=evidence_id
        )
        if not lock_evidence_for_attachment(evidence_id, photo_already_locked=True):
            from apps.evidence.storage import EvidenceObjectValidationError

            raise EvidenceObjectValidationError(
                "expired",
                "Evidence is expiring or has expired under the retention policy.",
            )
        if state.status == EvidenceUploadFinalization.Status.FINALIZED:
            return None, _result(state)
        if state.status == EvidenceUploadFinalization.Status.PROMOTING:
            stale_after = max(settings.EVIDENCE_URL_TTL_SECONDS, 60)
            if state.updated_at > timezone.now() - timedelta(seconds=stale_after):
                return None, None
        token = uuid.uuid4()
        state.status = EvidenceUploadFinalization.Status.PROMOTING
        state.claim_token = token
        state.save(update_fields=["status", "claim_token", "updated_at"])
        return token, None


def lock_evidence_for_attachment(evidence_id, *, photo_already_locked=False):
    """Use the retention lock order and reject evidence already claimed for expiry."""
    from apps.evidence.models import EvidenceObjectRetentionState

    if not photo_already_locked:
        EvidencePhoto.objects.select_for_update().get(pk=evidence_id)
        EvidenceUploadFinalization.objects.select_for_update().filter(
            evidence_id=evidence_id
        ).first()
    state = EvidenceObjectRetentionState.objects.select_for_update().filter(
        evidence_id=evidence_id
    ).first()
    return state is None


def _recover_or_wait(evidence, max_bytes):
    from apps.evidence import storage

    deadline = time.monotonic() + FINALIZATION_WAIT_SECONDS
    while True:
        state = EvidenceUploadFinalization.objects.get(evidence_id=evidence.pk)
        if state.status == EvidenceUploadFinalization.Status.FINALIZED:
            return _result(state)
        final = _validated_or_none(storage, evidence.object_key, max_bytes)
        if final is not None:
            return _complete(evidence.pk, final)
        if time.monotonic() >= deadline:
            raise FinalizationInProgress("Evidence finalization is already in progress.")
        time.sleep(FINALIZATION_POLL_SECONDS)


def _validated_or_none(storage, object_key, max_bytes):
    try:
        result = storage.validate_evidence_object(object_key)
    except storage.EvidenceObjectValidationError as exc:
        if exc.code == "missing":
            return None
        raise
    if not (1 <= result.size <= max_bytes):
        raise storage.EvidenceObjectValidationError(
            "too_large", "Evidence object exceeds the size limit."
        )
    return result


def _complete(evidence_id, result):
    with transaction.atomic():
        EvidencePhoto.objects.select_for_update().get(pk=evidence_id)
        state = EvidenceUploadFinalization.objects.select_for_update().get(
            evidence_id=evidence_id
        )
        if state.status == EvidenceUploadFinalization.Status.FINALIZED:
            return _result(state)
        state.status = EvidenceUploadFinalization.Status.FINALIZED
        state.claim_token = None
        state.size_bytes = result.size
        state.content_type = result.content_type
        state.save(
            update_fields=[
                "status",
                "claim_token",
                "size_bytes",
                "content_type",
                "updated_at",
            ]
        )
        return result


def _release_claim(evidence_id, claim_token):
    with transaction.atomic():
        EvidencePhoto.objects.select_for_update().get(pk=evidence_id)
        state = EvidenceUploadFinalization.objects.select_for_update().get(
            evidence_id=evidence_id
        )
        if (
            state.status == EvidenceUploadFinalization.Status.PROMOTING
            and state.claim_token == claim_token
        ):
            state.status = EvidenceUploadFinalization.Status.PENDING
            state.claim_token = None
            state.save(update_fields=["status", "claim_token", "updated_at"])


def _result(state):
    from apps.evidence.storage import EvidenceValidationResult

    return EvidenceValidationResult(
        size=state.size_bytes,
        content_type=state.content_type,
    )
