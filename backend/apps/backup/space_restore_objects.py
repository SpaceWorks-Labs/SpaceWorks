"""Object bytes across a per-space restore, after the database transaction commits.

Archived bytes come back under their ORIGINAL keys (identity, like the rows): a key whose
live bytes already match is left alone, a missing or different one is re-uploaded through
private staging and verified. Only after every archived object is verified are the
objects that only removed rows referenced deleted -- never the other way round.
Evidence photos are kept as rows, so their bytes are never in the removed set.
"""

import uuid

from apps.tenant_migration import object_storage
from apps.tenant_migration.object_storage import TenantObjectStorageError

from .archive_objects import collect_model_objects
from .space_restore_plan import KEPT_LIVE, SpaceRestoreError, live_queryset, restorable_labels


def referenced_keys(makerspace_id):
    """Every (bucket kind, key) the space's live dataset rows reference now."""
    from django.apps import apps

    result = {"private": {}, "public_image": {}}
    for label in (*restorable_labels(), *KEPT_LIVE):
        collect_model_objects(live_queryset(label, makerspace_id), apps.get_model(label), result)
    from apps.makerspaces.models import Makerspace
    collect_model_objects(Makerspace.objects.filter(pk=makerspace_id), Makerspace, result)
    return {(kind, key) for kind, keys in result.items() for key in keys}


def restore_objects(archive, operation_id):
    restored = verified = 0
    archived = set()
    for item in archive.objects():
        kind, key = item["bucket_kind"], item["key"]
        archived.add((kind, key))
        if item.get("retention_state") == "expired":
            continue
        if _matches(kind, key, item["sha256"]):
            verified += 1
            continue
        path = archive.object_path(item)
        if not path.is_file():
            raise SpaceRestoreError("archive_unreadable", f"Archived object {key!r} is missing.")
        staging = f"space-restores/{operation_id}/{uuid.uuid4().hex}"
        object_storage.upload_staged(staging, path)
        try:
            object_storage.copy_from_staging(staging, kind, key, item.get("content_type", ""))
        finally:
            object_storage.delete_object("private", staging)
        if not _matches(kind, key, item["sha256"]):
            raise SpaceRestoreError("object_verification_failed", f"Restored object {key!r} did not verify.")
        restored += 1
    return {"objects_verified": verified, "objects_restored": restored, "archived": archived}


def delete_unreferenced(before, after, archived):
    """Delete bytes only removed rows referenced; failures are reported, never raised."""
    deleted, failed = 0, 0
    for kind, key in sorted(before - after - archived):
        try:
            object_storage.delete_object(kind, key)
            deleted += 1
        except TenantObjectStorageError:
            failed += 1
    return {"objects_deleted": deleted, "object_deletes_failed": failed}


def _matches(kind, key, sha256):
    if not object_storage.object_exists(kind, key):
        return False
    return object_storage.digest_object(kind, key)[1] == sha256
