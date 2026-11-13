"""Object-storage collection, deletion and quota release for `module_purge` (split out).

Keys are collected under the purge's makerspace lock and deleted after commit,
best-effort. Re-exported from ``module_purge``; import them from there.
"""

import logging

from django.conf import settings

from apps.object_storage import delete_all_versions

logger = logging.getLogger("apps.makerspaces.module_purge")


def _collect_private_keys(makerspace, plan):
    from apps.backup.models import RestoreRollbackObject

    keys, seen = [], set()

    def add(key):
        if key and key not in seen:
            seen.add(key)
            keys.append(key)

    if plan.private_keys is not None:
        plan.private_keys(makerspace, add)
    for key in RestoreRollbackObject.objects.filter(
        makerspace=makerspace,
        module_key=plan.key,
        bucket_kind=RestoreRollbackObject.BucketKind.PRIVATE,
    ).exclude(copy_key="").values_list("copy_key", flat=True):
        add(key)
    return keys


def _collect_public_keys(makerspace, plan):
    from apps.backup.models import RestoreRollbackObject

    keys = list(plan.public_image_keys(makerspace)) if plan.public_image_keys is not None else []
    keys.extend(
        RestoreRollbackObject.objects.filter(
            makerspace=makerspace,
            module_key=plan.key,
            bucket_kind=RestoreRollbackObject.BucketKind.PUBLIC_IMAGE,
        ).exclude(copy_key="").values_list("copy_key", flat=True)
    )
    return [key for key in dict.fromkeys(keys) if key]


def _delete_private_keys(keys):
    """Best-effort delete of private objects; returns the keys the bucket confirmed gone.

    The return value is what lets the caller release storage quota for those keys only.
    A client that cannot even be constructed confirms nothing, so nothing is freed.
    """
    if not keys:
        return set()
    from apps.evidence import storage

    try:
        client = storage._client()
    except Exception:
        logger.exception("module_purge_storage_client_failed", extra={"keys": len(keys)})
        return set()
    deleted = set()
    for key in keys:
        try:
            delete_all_versions(
                client, bucket=settings.AWS_STORAGE_BUCKET_NAME, key=key
            )
        except Exception:
            logger.exception("module_purge_storage_delete_failed: %s", key)
        else:
            deleted.add(key)
    if deleted:
        from apps.backup.models import RestoreRollbackObject

        RestoreRollbackObject.objects.filter(copy_key__in=deleted).delete()
    return deleted


def _collect_private_key_sizes(makerspace, plan):
    from apps.backup.models import RestoreRollbackObject

    sizes = plan.private_key_sizes(makerspace) if plan.private_key_sizes is not None else {}
    sizes.update({
        key: size for key, size in RestoreRollbackObject.objects.filter(
            makerspace=makerspace,
            module_key=plan.key,
            bucket_kind=RestoreRollbackObject.BucketKind.PRIVATE,
        ).exclude(copy_key="").values_list("copy_key", "size_bytes")
    })
    return sizes


def _free_private_storage(makerspace, sizes, deleted_keys):
    """Release charged bytes for private objects that were confirmed deleted."""
    if not sizes or not deleted_keys:
        return
    from .models_page_cleanup import PublicPageObjectCleanup
    # The deletion callback may already have completed before this legacy path.
    # Both pending and completed page receipts own their quota release exactly once.
    journaled = set(PublicPageObjectCleanup.objects.filter(
        owner_kind__in=("makerspace", "event"), owner_id=makerspace.pk, object_key__in=deleted_keys,
    ).values_list("object_key", flat=True))
    freed = sum(
        size for key, size in sizes.items() if size and key in deleted_keys
        and key not in journaled
        # Artwork upload reservations cover the staging object too. A failed
        # staging deletion cannot grant the tenant that reserved budget back.
        and (not key.startswith("events/certificate-artwork/")
             or f"staging/{key}" in deleted_keys)
    )
    if not freed:
        return
    from apps.makerspaces import limits

    try:
        limits.free_storage(makerspace, freed)
    except Exception:
        logger.exception("module_purge_private_accounting_failed", extra={"bytes": freed})


def _delete_public_images_and_free_storage(makerspace, keys):
    if not keys:
        return
    from apps.inventory import public_image_storage

    # Freeing first when a best-effort delete silently failed makes the counter
    # permanently wrong in the direction that grants free storage.
    for key in keys:
        public_image_storage.release_public_image(makerspace, key)
        from apps.backup.models import RestoreRollbackObject

        RestoreRollbackObject.objects.filter(copy_key=key).delete()
