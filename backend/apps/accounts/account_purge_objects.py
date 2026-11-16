"""Crash-safe, separately committed byte deletion and storage quota release."""

from django.db import transaction
from django.utils import timezone

from apps.accounts.models_account_purge import AccountPurgeObject
from apps.audit import services as audit
from apps.inventory.public_image_storage import _client
from apps.makerspaces import limits
from apps.makerspaces.models import Makerspace
from apps.object_storage import delete_all_versions


def _locked(pk):
    # Quota writers take Makerspace first. Keep that order before journal locks.
    tenant = AccountPurgeObject.objects.values_list("makerspace_id", flat=True).get(pk=pk)
    space = Makerspace.objects.select_for_update().get(pk=tenant)
    return space, AccountPurgeObject.objects.select_for_update().get(pk=pk)


def delete_bytes(pk):
    with transaction.atomic():
        space, row = _locked(pk)
        if row.deleted_at is not None:
            return
        row.attempts += 1
        try:
            delete_all_versions(_client(), bucket=row.bucket, key=row.object_key)
        except Exception as exc:
            # Persist only a type, never an endpoint, key, token or response body.
            row.last_error = type(exc).__name__[:128]
            row.save(update_fields=["attempts", "last_error"])
            audit.record(None, "account.purge_object_retry", makerspace=space, target=row.user,
                         meta={"step": "delete", "attempts": row.attempts})
            return
        row.deleted_at = timezone.now()
        row.last_error = ""
        row.save(update_fields=["attempts", "last_error", "deleted_at"])
        audit.record(None, "account.purge_object_deleted", makerspace=space, target=row.user)


def release_quota(pk):
    with transaction.atomic():
        space, row = _locked(pk)
        if row.deleted_at is None or row.quota_released_at is not None:
            return
        # Exactly the accounting primitive used by release_public_image. The
        # decrement and stamp commit together, preventing duplicate releases.
        limits.free_storage(space, row.size_bytes)
        row.quota_released_at = timezone.now()
        row.last_error = ""
        row.save(update_fields=["quota_released_at", "last_error"])
        audit.record(None, "account.purge_object_quota_released", makerspace=space, target=row.user)


def drain(user, makerspace_id):
    ids = AccountPurgeObject.objects.filter(user=user, makerspace_id=makerspace_id,
                                          quota_released_at__isnull=True).values_list("pk", flat=True)
    for pk in list(ids):
        delete_bytes(pk)
        try:
            release_quota(pk)
        except Exception as exc:
            # The failed quota transaction rolled back both its decrement and
            # stamp. Keep a durable, non-sensitive diagnostic in a fresh one.
            with transaction.atomic():
                space, row = _locked(pk)
                row.attempts += 1
                row.last_error = type(exc).__name__[:128]
                row.save(update_fields=["attempts", "last_error"])
                audit.record(None, "account.purge_object_retry", makerspace=space, target=row.user,
                             meta={"step": "quota", "attempts": row.attempts})
