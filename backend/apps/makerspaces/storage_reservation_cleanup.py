"""Expiry releases byte debt only after deletion; receipts keep reconciling late writes.

Evidence metadata is retained. This never invokes abandoned-photo row cleanup and
does not change its deployment switch or tenant opt-in.
"""
import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.audit.services import record
from .models import Makerspace
from .models_storage_reservations import StorageQuotaReservation as Reservation

logger = logging.getLogger(__name__)


@transaction.atomic
def cleanup(reservation_id, *, now=None, cancel=False):
    from django.conf import settings
    from apps.evidence import storage
    from apps.evidence.models import EvidencePhoto, EvidenceObjectRetentionState, EvidenceUploadFinalization
    from apps.object_storage import delete_all_versions

    now = now or timezone.now()
    found = Reservation.objects.get(pk=reservation_id)
    # Domain workflows hold the space before the photo; legacy retention holds
    # the photo first. Cleanup never waits on either owner, so it cannot close
    # a space/photo deadlock cycle. The sweeper retries a busy receipt later.
    space = Makerspace.objects.select_for_update(no_key=True, nowait=True).filter(pk=found.makerspace_id).first()
    photo = EvidencePhoto.objects.select_for_update(nowait=True).filter(object_key=found.object_key).first()
    finalization = None
    if photo is not None:
        finalization = EvidenceUploadFinalization.objects.select_for_update(nowait=True).filter(evidence=photo).first()
        retention = EvidenceObjectRetentionState.objects.select_for_update(nowait=True).filter(evidence=photo).first()
        if retention is not None and retention.status in {"cleaning", "expiring"}:
            return False
    row = Reservation.objects.select_for_update().get(pk=reservation_id)
    if cancel and not row.object_key.startswith(f"card-photo-batches/{row.makerspace_id}/"):
        raise ValueError("Only server-owned batch photos may be cancelled before expiry.")
    if row.expires_at > now and not cancel:
        return False
    if row.storage_endpoint != (settings.AWS_S3_ENDPOINT_URL or ""):
        raise storage.StorageUnavailable("Upload storage identity has changed.")
    if finalization and finalization.status == "promoting":
        lease = timedelta(seconds=max(settings.EVIDENCE_URL_TTL_SECONDS, 60))
        if finalization.updated_at > now - lease:
            return False  # A live promoter still owns these bytes.
        if row.converted or photo.consumption_state == "consumed":
            return False
        # Same photo -> finalization -> retention lock order as attachment.
        # The retained sidecar fences a crashed promoter's late completion and
        # all later attachment attempts, independently of cleanup opt-ins.
        EvidenceObjectRetentionState.objects.get_or_create(evidence=photo, defaults={
            "status": "expired", "object_expired_at": now, "expired_size_bytes": 0,
        })
        finalization.status, finalization.claim_token = "pending", None
        finalization.save(update_fields=["status", "claim_token", "updated_at"])
    # A converted attachment owns its final bytes. Only its staging key is disposable.
    keys = {(row.bucket, row.staging_key)}
    if not row.converted or space is None:
        if photo is not None and photo.consumption_state == "consumed":
            return False  # Fail closed on inconsistent legacy/domain state.
        keys.update([(row.final_bucket, row.object_key), (row.final_bucket, row.final_key)])
    client = storage._client()
    for bucket, key in sorted(keys):
        result = delete_all_versions(client, bucket=bucket, key=key)
        if not result.absence_confirmed:
            raise storage.StorageUnavailable("Upload deletion was not confirmed.")
    first = not row.released
    row.released, row.cleaning = True, False
    # Keep reconciling: a request accepted just before expiry can finish late.
    row.expires_at = now + timedelta(hours=6)
    row.save(update_fields=["released", "cleaning", "expires_at"])
    if photo is not None and not row.converted:
        EvidenceObjectRetentionState.objects.get_or_create(evidence=photo, defaults={
            "status": "expired", "object_expired_at": now, "expired_size_bytes": 0,
        })
    if first:
        record(None, "storage.upload_reservation_released", makerspace=space, target=space,
               meta={"reserved_bytes": row.size_bytes, "converted": row.converted})
    return True


def sweep(limit=100):
    from apps.tenant_migration.gate_runtime import fanout_tenant_write
    rows = Reservation.objects.filter(expires_at__lte=timezone.now()).order_by("expires_at", "pk")
    released = 0
    counts = {}
    for row_id, space_id in rows.values_list("pk", "makerspace_id")[:limit]:
        try:
            if not Makerspace.objects.filter(pk=space_id).exists():
                # No tenant remains to admit a writer. The server-owned receipt
                # still owns exact-key deletion, retaining its original RLS id.
                from apps.tenant_rls.context import tenant_context
                with tenant_context(space_id, label="storage_upload_reservation_cleanup"):
                    released += int(cleanup(row_id))
                continue
            with fanout_tenant_write(space_id, operation="public_page_asset_cleanup", counts=counts) as admitted:
                if not admitted:
                    continue
                released += int(cleanup(row_id))
        except Exception:
            logger.exception("storage_upload_reservation_cleanup_failed", extra={"reservation_id": row_id})
    return released
