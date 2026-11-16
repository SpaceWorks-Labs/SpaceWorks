import io
from threading import Lock
from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError

from apps.storage_capabilities.contracts import CapabilityError
from apps.storage_capabilities.probes import inspect_bucket, probe_conditional_create
from tests.cloud.storage.test_contracts import contract


class AtomicStore:
    def __init__(self, *, ignores_condition=False):
        self.objects = {}
        self.lock = Lock()
        self.ignores_condition = ignores_condition

    def put_object(self, *, Bucket, Key, Body, IfNoneMatch):
        with self.lock:
            if Key in self.objects and not self.ignores_condition:
                raise ClientError({"Error": {"Code": "PreconditionFailed"}}, "PutObject")
            self.objects[Key] = Body
        return {}

    def get_object(self, *, Bucket, Key):
        with self.lock:
            return {"Body": io.BytesIO(self.objects[Key])}

    def delete_object(self, *, Bucket, Key):
        self.objects.pop(Key, None)

    def head_object(self, *, Bucket, Key):
        if Key not in self.objects:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "HeadObject")
        return {}


def test_conditional_probe_has_one_winner_and_cleans_its_only_key():
    s3 = AtomicStore()
    assert probe_conditional_create(s3, bucket="b", never_versioned=True)
    assert not s3.objects


def test_provider_ignoring_header_is_not_certified():
    s3 = AtomicStore(ignores_condition=True)
    with pytest.raises(CapabilityError, match="unproven"):
        probe_conditional_create(s3, bucket="b", never_versioned=True)
    assert not s3.objects


def test_unknown_versioning_is_not_false_or_never_versioned():
    s3 = Mock()
    s3.get_bucket_versioning.side_effect = ClientError({"Error": {"Code": "AccessDenied"}}, "GetBucketVersioning")
    with pytest.raises(CapabilityError, match="unknown"):
        inspect_bucket(s3, contract())
    s3.put_bucket_versioning.assert_not_called()


def test_r2_style_unsupported_requires_explicit_never_versioned_declaration():
    s3 = Mock()
    s3.get_bucket_versioning.side_effect = ClientError({"Error": {"Code": "NotImplemented"}}, "GetBucketVersioning")
    s3.list_object_versions.side_effect = ClientError({"Error": {"Code": "NotImplemented"}}, "ListObjectVersions")
    assert inspect_bucket(s3, contract())["versioning_source"] == "declared_without_version_api"
    with pytest.raises(CapabilityError):
        inspect_bucket(s3, contract(versioning="unknown"))


def test_b2_without_post_keeps_version_history():
    s3 = Mock()
    s3.get_bucket_versioning.return_value = {"Status": "Enabled"}
    facts = inspect_bucket(s3, contract(versioning="enabled", list_delete_versions=True))
    assert facts["versioning"] == "enabled"
    assert facts["list_delete_versions"] is True
    s3.put_bucket_versioning.assert_not_called()


def test_misdeclared_limited_bucket_cannot_hide_b2_style_history():
    s3 = Mock()
    s3.get_bucket_versioning.return_value = {}
    s3.list_object_versions.return_value = {"Versions": [{"Key": "old", "VersionId": "real-version"}]}
    with pytest.raises(CapabilityError, match="history_observed"):
        inspect_bucket(s3, contract())
