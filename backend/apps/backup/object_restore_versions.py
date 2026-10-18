"""Deterministic version-history handling for object restore rollback."""

from apps.storage_capabilities import capabilities_for
from apps.storage_capabilities.budget import checkpoint
from apps.storage_capabilities.deletion import version_pages


class ObjectRestoreError(RuntimeError):
    pass


def current_delete_marker_version_id(client, bucket, key):
    for item in _iter_key_versions_newest_first(client, bucket, key):
        if item["is_delete_marker"]:
            return item["version_id"]
        raise ObjectRestoreError(
            f"Could not identify the current delete marker for {key}."
        )
    return ""


def delete_versions_newer_than_marker(client, *, bucket, key, marker_version_id):
    newer_versions = []
    for item in _iter_key_versions_newest_first(client, bucket, key):
        if item["version_id"] == marker_version_id:
            if not item["is_delete_marker"]:
                raise ObjectRestoreError("Rollback marker does not identify a delete marker.")
            for version_id in newer_versions:
                checkpoint()
                client.delete_object(Bucket=bucket, Key=key, VersionId=version_id)
            remaining = next(_iter_key_versions_newest_first(client, bucket, key), None)
            if remaining is None or remaining["version_id"] != marker_version_id or not remaining["is_delete_marker"]:
                raise ObjectRestoreError("Rollback version absence could not be proved.")
            return
        newer_versions.append(item["version_id"])
    raise ObjectRestoreError(
        f"Rollback delete marker {marker_version_id} was not found for {key}."
    )


def _iter_key_versions_newest_first(client, bucket, key):
    # MaxKeys=1 preserves S3's version order without merging the separately
    # returned Versions and DeleteMarkers arrays or comparing timestamps.
    contract = capabilities_for(client, bucket)
    if contract is not None and contract.list_delete_versions is not True:
        raise ObjectRestoreError("Version-history rollback is unavailable for this bucket.")
    for page in version_pages(client, bucket=bucket, prefix=key, max_keys=1):
        for field, is_delete_marker in (
            ("Versions", False),
            ("DeleteMarkers", True),
        ):
            for item in page.get(field, ()):
                if item.get("Key") == key:
                    yield {
                        "version_id": item["VersionId"],
                        "is_delete_marker": is_delete_marker,
                    }
