import io
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError

from apps.storage_capabilities import promotion
from apps.storage_capabilities.contracts import CapabilityError


@pytest.fixture
def s3(monkeypatch):
    monkeypatch.setattr(promotion, "require_capability", lambda *args: None)
    result = Mock()
    result.head_object.return_value = {"ContentLength": 5, "ETag": '"staging-1"'}
    result.get_object.side_effect = lambda **kwargs: {"Body": io.BytesIO(b"hello"), "ContentType": "image/png"}
    result.put_object.return_value = {}
    return result


def promote(s3, **changes):
    return promotion.promote(s3, **{
        "source_bucket": "private", "source_key": "staging/image",
        "destination_bucket": "public", "destination_key": "image", "max_bytes": 5,
        **changes,
    })


def test_private_snapshot_is_pinned_validated_and_put_with_create_only(s3):
    sent = {}
    def put(**kwargs):
        sent.update(kwargs)
        sent["bytes"] = kwargs["Body"].read()
        return {}
    s3.put_object.side_effect = put
    def validate(spool, size):
        assert size == 5 and spool.read() == b"hello"
        return "image/jpeg"
    result = promote(s3, validate=validate)
    assert result["size"] == 5
    assert sent["IfNoneMatch"] == "*" and sent["bytes"] == b"hello"
    assert sent["ContentType"] == "image/jpeg"
    assert s3.get_object.call_args_list[0].kwargs["IfMatch"] == '"staging-1"'
    assert s3.get_object.call_args_list[0].kwargs["Bucket"] == "private"
    assert sent["Bucket"] == "public"


def test_oversize_or_false_head_never_creates_final(s3):
    s3.get_object.side_effect = lambda **kwargs: {"Body": io.BytesIO(b"hello-too-large")}
    with pytest.raises(CapabilityError, match="size_invalid"):
        promote(s3)
    s3.put_object.assert_not_called()


def test_validation_failure_and_expired_lease_leave_no_final(s3):
    def invalid(*args):
        raise ValueError("bad bytes")
    with pytest.raises(ValueError):
        promote(s3, validate=invalid)
    s3.put_object.assert_not_called()


def test_existing_final_is_never_overwritten(s3):
    s3.put_object.side_effect = ClientError({"Error": {"Code": "PreconditionFailed"},
                                          "ResponseMetadata": {"HTTPStatusCode": 412}}, "PutObject")
    with pytest.raises(CapabilityError, match="already_exists"):
        promote(s3)


def test_versioned_source_is_pinned_by_version(s3):
    s3.head_object.return_value["VersionId"] = "version-1"
    promote(s3)
    assert s3.get_object.call_args_list[0].kwargs["VersionId"] == "version-1"


def test_changed_etag_fails_before_read_or_write(s3):
    with pytest.raises(CapabilityError, match="staging_changed"):
        promote(s3, expected_etag='"old"')
    s3.get_object.assert_not_called()
    s3.put_object.assert_not_called()
