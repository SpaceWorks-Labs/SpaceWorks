"""Durable all-version reconciliation. Locators never expire or follow an FK."""
from datetime import timedelta
from uuid import uuid4
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from apps.audit.services import record
from .cleanup_models import FinanceObjectCleanup
from .attachment_storage import FinanceStorage


def delete_one(cleanup_id, *, storage=None):
    from apps.backup.models import DeploymentRecoveryState
    if not DeploymentRecoveryState.objects.filter(pk=1, mode=DeploymentRecoveryState.Mode.NORMAL).exists():
        return False
    token, now = uuid4(), timezone.now()
    # This is deployment cleanup capability, not a tenant mutation or interactive
    # finance authority. It must still run after MIGRATED_OUT/whole-tenant purge.
    with transaction.atomic():
        row = FinanceObjectCleanup.objects.select_for_update().get(pk=cleanup_id)
        if row.next_attempt_at is None or row.next_attempt_at > now or row.lease_until and row.lease_until > now:
            return False
        row.lease_token, row.lease_until, row.attempts = token, now + timedelta(minutes=5), row.attempts + 1
        row.save(update_fields=["lease_token", "lease_until", "attempts"])
    ok = False
    try:
        storage = storage or FinanceStorage(bucket_name=row.bucket)
        for key in (row.staging_key, row.object_key):
            if not DeploymentRecoveryState.objects.filter(pk=1, mode=DeploymentRecoveryState.Mode.NORMAL).exists():
                raise RuntimeError("Deployment recovery fence closed.")
            storage.delete(key)
        ok = True
    except Exception:
        # No SDK exception, object name, filename or value in log/audit/error.
        pass
    with transaction.atomic():
        fresh = FinanceObjectCleanup.objects.select_for_update().get(pk=row.pk)
        if fresh.lease_token != token:
            return False
        fresh.lease_token = fresh.lease_until = None
        fresh.next_attempt_at = timezone.now() + timedelta(hours=6 if ok else 12)
        fresh.last_error_code = "" if ok else "storage_delete_unavailable"
        if ok:
            fresh.deleted_at = timezone.now()
        fresh.save()
        record(None, "finance.attachment.cleanup_complete" if ok else "finance.attachment.cleanup_retry",
            target=fresh, meta={"cleanup_id": str(fresh.pk), "asset_id": fresh.asset_id, "attempts": fresh.attempts})
    if ok:
        # Source gates may prevent the projection update. The permanent locator
        # remains complete and retries independently; no bytes become readable.
        from .attachment_models import FinanceAttachment
        from .worker_boundary import locked_asset
        from .attachment_workflow import mark_deleted_locked
        try:
            if FinanceAttachment.objects.filter(pk=row.asset_id, state__in=("expired", "deleting")).exists():
                with locked_asset(row.asset_id) as (asset, obligation):
                    mark_deleted_locked(asset, now=timezone.now(), cleanup_id=row.pk)
        except Exception:
            pass
    return ok


def due_ids(*, now, limit=100):
    return tuple(FinanceObjectCleanup.objects.filter(next_attempt_at__lte=now).filter(
        Q(lease_until__isnull=True) | Q(lease_until__lte=now)).order_by("next_attempt_at", "pk").values_list("pk", flat=True)[:limit])


def collect_tenant_locked(makerspace_id):
    """G calls BEFORE whole-tenant deletion, in that same transaction."""
    from .attachment_models import FinanceAttachment
    from .attachment_storage import bucket
    for asset in FinanceAttachment.objects.filter(makerspace_id=makerspace_id).iterator(chunk_size=100):
        locator, _ = FinanceObjectCleanup.objects.get_or_create(asset_id=asset.pk, defaults={
            "source_makerspace_id": makerspace_id, "bucket": bucket(),
            "staging_key": asset.staging_key, "object_key": asset.object_key})
        locator.next_attempt_at = timezone.now()
        locator.save(update_fields=["next_attempt_at"])


def reserved_key(key):
    return FinanceObjectCleanup.objects.filter(Q(staging_key=key) | Q(object_key=key)).exists()
