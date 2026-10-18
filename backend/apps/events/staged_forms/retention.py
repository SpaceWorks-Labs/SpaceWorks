"""Permanent cleanup tombstones retry both keys, including after source purge."""
from datetime import timedelta
from uuid import uuid4
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from .upload_models import StageFileCleanup, StageFormAsset


def register_imported_locked(assets):
    """After G remaps object keys; never import source cleanup receipts as jobs."""
    from django.conf import settings
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("Use the enclosing tenant import transaction.")
    for asset in assets:
        due = asset.expires_at or timezone.now() + timedelta(hours=24)
        values = {"tenant_id": asset.event.makerspace_id, "event_id_snapshot": asset.event_id,
            "bucket": settings.AWS_STORAGE_BUCKET_NAME, "staging_key": asset.staging_key, "object_key": asset.object_key}
        row, created = StageFileCleanup.objects.get_or_create(source_asset_id=asset.pk,
            defaults={**values, "not_before": due, "next_attempt_at": due})
        if not created and any(getattr(row, key) != value for key, value in values.items()):
            raise ValueError("Stage cleanup locator collision.")


def cleanup_one(cleanup_id, *, store=None):
    from apps.tenant_migration.gate_locks import shared_boundary
    seed = StageFileCleanup.objects.get(pk=cleanup_id)
    # Keep a signed target-abort reopening from racing receipt-only deletion on
    # a migrated-out source. The separate connection transacts locks only.
    with shared_boundary(seed.tenant_id):
        return _cleanup_receipt(seed, store=store)


def _cleanup_receipt(seed, *, store=None):
    from .storage import storage
    from .upload_jobs import locked_asset
    from .upload_workflow import expire_locked, deleted_locked
    now = timezone.now()
    from apps.tenant_migration.models_source_gate import SourceMigrationGate
    migrated = SourceMigrationGate.objects.filter(makerspace_id=seed.tenant_id, state="migrated_out").exists()
    # Normal expiry serializes with attachment under event -> asset locks.
    # A migrated-out source under the boundary has no new attachments; its independent
    # receipt is authoritative and no frozen domain row is mutated or decrypted.
    asset = None if migrated else StageFormAsset.objects.filter(pk=seed.source_asset_id).first()
    if asset:
        with locked_asset(asset, runtime=False) as row:
            if row.expires_at is None or row.expires_at > now:
                StageFileCleanup.objects.filter(pk=seed.pk).update(next_attempt_at=row.expires_at or now + timedelta(days=1))
                return False
            expire_locked(row, now=now)
    with transaction.atomic():
        row = StageFileCleanup.objects.select_for_update().get(pk=seed.pk)
        if row.not_before > now or row.next_attempt_at > now or row.lease_until and row.lease_until > now:
            return False
        row.lease_token, row.lease_until = uuid4(), now + timedelta(minutes=5)
        row.attempts += 1
        row.save()
        token, keys, bucket = row.lease_token, (row.staging_key, row.object_key), row.bucket
    error = ""
    try:
        store = store or storage()
        store.bucket = bucket
        store.delete(keys)
    except Exception:
        error = "storage_cleanup_pending"
    with transaction.atomic():
        row = StageFileCleanup.objects.select_for_update().get(pk=seed.pk)
        if row.lease_token != token:
            return False
        row.lease_token, row.lease_until, row.last_error_code = None, None, error
        row.next_attempt_at = now + timedelta(minutes=720 if error else 360)
        if not error:
            row.last_deleted_at = now
        row.save()
    if not error and asset and StageFormAsset.objects.filter(pk=asset.pk).exists():
        with locked_asset(asset, runtime=False) as current:
            deleted_locked(current, now=now)
    return not error


def sweep(*, limit=100):
    import logging
    logger = logging.getLogger(__name__)
    now = timezone.now()
    ids = StageFileCleanup.objects.filter(next_attempt_at__lte=now, not_before__lte=now).filter(
        Q(lease_until__isnull=True) | Q(lease_until__lte=now)).order_by("next_attempt_at", "pk").values_list("pk", flat=True)[:min(limit, 100)]
    count = 0
    for pk in list(ids):
        try:
            count += bool(cleanup_one(pk))
        except Exception:
            logger.warning("stage_file_cleanup_retry", extra={"cleanup_id": pk})
    return count
