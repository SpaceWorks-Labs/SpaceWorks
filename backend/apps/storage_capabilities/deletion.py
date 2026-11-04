"""Exact-key deletion with physical absence proof; no unsupported-API fallback."""

from dataclasses import dataclass

from botocore.exceptions import ClientError

from .contracts import CapabilityError
from .budget import checkpoint


@dataclass(frozen=True)
class DeletionEvidence:
    key: str
    versions_deleted: int
    absence_confirmed: bool = True
    bytes_observed: int | None = None


def version_pages(client, *, bucket, prefix, max_keys=1000):
    params = {"Bucket": bucket, "Prefix": prefix, "MaxKeys": max_keys}
    seen = set()
    while True:
        checkpoint()
        page = client.list_object_versions(**params)
        yield page
        if not page.get("IsTruncated"):
            return
        marker = (page.get("NextKeyMarker"), page.get("NextVersionIdMarker"))
        if not marker[0] or marker in seen:
            raise CapabilityError("storage_version_pagination_invalid")
        seen.add(marker)
        params.update(KeyMarker=marker[0])
        if marker[1] is not None:
            params["VersionIdMarker"] = marker[1]
        else:
            params.pop("VersionIdMarker", None)


def exact_versions(page, key):
    return [
        {"Key": key, "VersionId": item["VersionId"]}
        for name in ("Versions", "DeleteMarkers")
        for item in page.get(name, ()) if item.get("Key") == key
    ]


def assert_head_absent(client, *, bucket, key):
    try:
        checkpoint()
        client.head_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        if code in {"404", "NoSuchKey", "NotFound"}:
            return
        raise
    raise CapabilityError("storage_object_still_present")


def assert_exact_absent(client, *, bucket, key, never_versioned=False):
    if not never_versioned:
        for page in version_pages(client, bucket=bucket, prefix=key):
            if exact_versions(page, key):
                raise CapabilityError("storage_versions_still_present")
    assert_head_absent(client, bucket=bucket, key=key)


def delete_exact_key(client, *, bucket, key, never_versioned=False):
    if not isinstance(key, str) or not key or "\x00" in key:
        raise CapabilityError("storage_object_key_invalid")
    deleted = 0
    observed = 0
    sizes_known = True
    if never_versioned:
        try:
            checkpoint()
            size = client.head_object(Bucket=bucket, Key=key).get("ContentLength")
            sizes_known = type(size) is int and size >= 0
            observed = size if sizes_known else 0
        except ClientError as exc:
            if str(exc.response.get("Error", {}).get("Code", "")) not in {"404", "NoSuchKey", "NotFound"}:
                raise
        checkpoint()
        client.delete_object(Bucket=bucket, Key=key)
    else:
        for page in version_pages(client, bucket=bucket, prefix=key):
            objects = exact_versions(page, key)
            for item in page.get("Versions", ()):
                if item.get("Key") == key:
                    size = item.get("Size")
                    if type(size) is int and size >= 0:
                        observed += size
                    else:
                        sizes_known = False
            if objects:
                checkpoint()
                response = client.delete_objects(
                    Bucket=bucket, Delete={"Objects": objects, "Quiet": True},
                )
                if (response or {}).get("Errors"):
                    raise CapabilityError("storage_version_delete_failed")
                deleted += len(objects)
    assert_exact_absent(client, bucket=bucket, key=key, never_versioned=never_versioned)
    return DeletionEvidence(key, deleted, bytes_observed=observed if sizes_known else None)


def delete_owned_prefix(client, *, bucket, prefix, never_versioned=False):
    """Only a caller-owned directory, never an adjacent lexical prefix."""
    if not isinstance(prefix, str) or not prefix or not prefix.endswith("/") or prefix in {"/", "staging/"}:
        raise CapabilityError("storage_owned_prefix_required")
    if never_versioned:
        params = {"Bucket": bucket, "Prefix": prefix, "MaxKeys": 1000}
        seen = set()
        while True:
            checkpoint()
            page = client.list_objects_v2(**params)
            for item in page.get("Contents", ()):
                key = item["Key"]
                if not key.startswith(prefix):
                    raise CapabilityError("storage_prefix_listing_mismatch")
                delete_exact_key(client, bucket=bucket, key=key, never_versioned=True)
            if not page.get("IsTruncated"):
                break
            token = page.get("NextContinuationToken")
            if not token or token in seen:
                raise CapabilityError("storage_object_pagination_invalid")
            seen.add(token)
            params["ContinuationToken"] = token
    else:
        for page in version_pages(client, bucket=bucket, prefix=prefix):
            objects = [
                {"Key": item["Key"], "VersionId": item["VersionId"]}
                for name in ("Versions", "DeleteMarkers")
                for item in page.get(name, ())
            ]
            if any(not item["Key"].startswith(prefix) for item in objects):
                raise CapabilityError("storage_prefix_listing_mismatch")
            if objects:
                checkpoint()
                result = client.delete_objects(Bucket=bucket, Delete={"Objects": objects, "Quiet": True})
                if result.get("Errors"):
                    raise CapabilityError("storage_version_delete_failed")
        for page in version_pages(client, bucket=bucket, prefix=prefix):
            if page.get("Versions") or page.get("DeleteMarkers"):
                raise CapabilityError("storage_versions_still_present")
    checkpoint()
    if client.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=1).get("Contents"):
        raise CapabilityError("storage_object_still_present")
