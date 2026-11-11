import hashlib
import io
from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError

from apps.backup import storage
from tests.cloud.storage.test_contracts import contract


def test_capture_never_enables_versioning(monkeypatch):
    s3 = Mock()
    s3.get_bucket_versioning.return_value = {"Status": "Enabled"}
    monkeypatch.setattr(storage, "client", lambda: s3)
    monkeypatch.setattr(storage, "capabilities_for", lambda *args, **kwargs: None)
    assert storage.ensure_versioning_or_quiescence("private") == "versioned"
    s3.put_bucket_versioning.assert_not_called()


def test_capture_auth_failure_is_not_quiesced(monkeypatch):
    s3 = Mock()
    s3.get_bucket_versioning.side_effect = ClientError({"Error": {"Code": "AccessDenied"}}, "GetBucketVersioning")
    monkeypatch.setattr(storage, "client", lambda: s3)
    monkeypatch.setattr(storage, "capabilities_for", lambda *args, **kwargs: None)
    with pytest.raises(storage.BackupStorageError, match="could not be verified"):
        storage.ensure_versioning_or_quiescence("private")


def test_capture_pins_version_preserves_metadata_and_streams_digest(monkeypatch, tmp_path):
    s3 = Mock()
    s3.head_object.return_value = {"VersionId": "version-1"}
    body = io.BytesIO(b"captured bytes")
    s3.get_object.return_value = {"Body": body, "ContentLength": 14,
        "Metadata": {"origin": "test"}, "ContentType": "image/png", "CacheControl": "private"}
    monkeypatch.setattr(storage, "client", lambda: s3)
    result = storage.download_object("private", "image", tmp_path / "image", versioned=True)
    assert s3.get_object.call_args.kwargs["VersionId"] == "version-1"
    assert result["sha256"] == hashlib.sha256(b"captured bytes").hexdigest()
    assert result["metadata"] == {"origin": "test"}
    assert result["headers"]["CacheControl"] == "private"
    assert body.closed


def test_capture_only_falls_back_to_staging_on_missing_object(monkeypatch, tmp_path):
    s3 = Mock()
    s3.get_object.side_effect = ClientError({"Error": {"Code": "AccessDenied"}}, "GetObject")
    monkeypatch.setattr(storage, "client", lambda: s3)
    with pytest.raises(storage.BackupStorageError):
        storage.download_object("private", "image", tmp_path / "image", versioned=False)
    assert s3.get_object.call_count == 1
