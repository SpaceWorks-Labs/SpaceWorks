"""SECFIX-A F2, M7 / lead 3: machine-service and adapter-artifact uploads land on STAGING in both presign modes and
are promoted to the final key exactly once, pinned to the measured object; strict purges and signed downloads.

Runs against an in-memory S3 that models versions and ETags (no network, no database)."""
import hashlib

import pytest
from botocore.exceptions import ClientError

from apps.evidence.storage import StorageUnavailable
from apps.machines import service_storage


def _error(code, status):
    return ClientError({"Error": {"Code": code}, "ResponseMetadata": {"HTTPStatusCode": status}}, "Op")


class FakeS3:
    """Only the operations service_storage uses. ``objects[key]`` is a list of (version, etag, bytes)."""

    def __init__(self, versioned):
        self.versioned, self.objects, self.signed, self.copies = versioned, {}, [], []
        self.before_copy = None

    def put(self, key, data):
        rows = self.objects.setdefault(key, [])
        version = f"v{len(rows) + 1}" if self.versioned else None
        if not self.versioned:
            rows.clear()
        rows.append((version, '"%s"' % hashlib.md5(data).hexdigest(), data))

    def data(self, key):
        return self.objects[key][-1][2] if self.objects.get(key) else None

    def head_object(self, *, Bucket, Key):
        if not self.objects.get(Key):
            raise _error("404", 404)
        version, etag, data = self.objects[Key][-1]
        return {"ContentLength": len(data), "ETag": etag, **({"VersionId": version} if version else {})}

    def copy_object(self, *, Bucket, CopySource, Key, CopySourceIfMatch=None):
        if self.before_copy:
            hook, self.before_copy = self.before_copy, None
            hook()
        rows = self.objects.get(CopySource["Key"], [])
        if "VersionId" in CopySource:
            rows = [row for row in rows if row[0] == CopySource["VersionId"]]
        if not rows:
            raise _error("NoSuchKey", 404)
        _version, etag, data = rows[-1]
        if CopySourceIfMatch is not None and etag != CopySourceIfMatch:
            raise _error("PreconditionFailed", 412)
        self.copies.append(dict(CopySource, IfMatch=CopySourceIfMatch))
        self.put(Key, data)
        return {}

    def generate_presigned_post(self, **kwargs):
        self.signed.append(("post", kwargs["Key"], kwargs))
        return {"url": "https://objects.test", "fields": {"key": kwargs["Key"]}}

    def generate_presigned_url(self, operation, *, Params, ExpiresIn):
        self.signed.append((operation, Params["Key"], Params))
        return "https://objects.test/signed"


@pytest.fixture(params=[True, False], ids=["versioned", "unversioned"])
def store(request, monkeypatch):
    s3 = FakeS3(versioned=request.param)
    monkeypatch.setattr(service_storage, "_client", lambda: s3)
    monkeypatch.setattr(service_storage, "_public_client", lambda: s3)

    def delete_all_versions(client, *, bucket, key, **_kwargs):
        s3.objects.pop(key, None)
    monkeypatch.setattr(service_storage, "delete_all_versions", delete_all_versions)
    return s3


KEY = "machine/1/queue-1/service/abc"
STAGING = f"staging/{KEY}"


@pytest.mark.parametrize("method", ["post", "put"])
def test_both_presign_modes_sign_the_staging_key_never_the_final_one(store, settings, method):
    settings.STORAGE_PRESIGN_METHOD = method
    service_storage.presigned_upload(KEY, "application/pdf", 1024)
    (_op, signed_key, _params), = store.signed
    assert signed_key == STAGING  # the attack: a POST presign used to sign KEY itself


@pytest.mark.parametrize("method", ["post", "put"])
def test_finalize_promotes_once_and_a_replayed_presign_cannot_replace_the_accepted_object(store, settings, method):
    settings.STORAGE_PRESIGN_METHOD = method
    store.put(STAGING, b"validated bytes")
    assert service_storage.finalize_upload(KEY, 1024) == len(b"validated bytes")
    assert store.data(KEY) == b"validated bytes" and store.data(STAGING) is None
    # The still-valid presign is replayed with different bytes after the object was accepted.
    store.put(STAGING, b"swapped, never validated")
    assert service_storage.finalize_upload(KEY, 1024) == len(b"validated bytes")
    assert store.data(KEY) == b"validated bytes"
    assert store.data(STAGING) is None  # the replayed upload is discarded, never promoted


def test_promotion_is_pinned_to_the_object_that_was_measured(store, settings):
    settings.STORAGE_PRESIGN_METHOD = "put"
    store.put(STAGING, b"small")
    store.before_copy = lambda: store.put(STAGING, b"a much larger object swapped in mid-promotion")
    if store.versioned:
        assert service_storage.finalize_upload(KEY, 10) == len(b"small")
        assert store.data(KEY) == b"small" and store.copies[0]["VersionId"] == "v1"
    else:
        with pytest.raises(StorageUnavailable):  # the ETag precondition refuses the swapped object
            service_storage.finalize_upload(KEY, 10)
        assert store.data(KEY) is None and store.copies == []


def test_an_oversized_or_missing_upload_is_never_promoted(store):
    assert service_storage.finalize_upload(KEY, 4) is None
    store.put(STAGING, b"too large")
    assert service_storage.finalize_upload(KEY, 4) == len(b"too large")
    assert store.data(KEY) is None


def test_a_legacy_final_object_from_an_old_post_presign_still_finalizes(store):
    store.put(KEY, b"legacy")
    assert service_storage.finalize_upload(KEY, 1024) == len(b"legacy")
    assert store.data(KEY) == b"legacy"


def test_purge_upload_deletes_both_keys_and_raises_when_storage_fails(store, monkeypatch):
    store.put(KEY, b"final")
    store.put(STAGING, b"staged")
    service_storage.purge_upload(KEY)
    assert store.data(KEY) is None and store.data(STAGING) is None

    def broken(client, *, bucket, key, **_kwargs):
        raise _error("InternalError", 500)
    monkeypatch.setattr(service_storage, "delete_all_versions", broken)
    with pytest.raises(StorageUnavailable):  # never swallowed: the caller must not mark the row purged
        service_storage.purge_upload(KEY)
    service_storage.cleanup_upload(KEY)  # the best-effort compensation path still never raises


def test_signed_downloads_are_attachments_with_a_fixed_type(store):
    service_storage.presigned_download_url("adapter-artifacts/1/b/x", "image/png")
    (op, key, params), = store.signed
    assert op == "get_object" and key == "adapter-artifacts/1/b/x"
    assert params["ResponseContentDisposition"] == "attachment" and params["ResponseContentType"] == "image/png"
