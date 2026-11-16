from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError

from apps.storage_capabilities.contracts import CapabilityError
from apps.storage_capabilities.deletion import assert_exact_absent, delete_exact_key, delete_owned_prefix


def missing():
    return ClientError({"Error": {"Code": "NoSuchKey"}}, "HeadObject")


def test_never_versioned_delete_requires_successful_absence_check():
    s3 = Mock()
    s3.head_object.side_effect = missing()
    result = delete_exact_key(s3, bucket="b", key="exact", never_versioned=True)
    assert result.absence_confirmed
    assert result.versions_deleted == 0
    s3.list_object_versions.assert_not_called()
    s3.delete_object.assert_called_once_with(Bucket="b", Key="exact")


@pytest.mark.parametrize("failure", [
    ClientError({"Error": {"Code": "NotImplemented"}}, "ListObjectVersions"),
    ClientError({"Error": {"Code": "AccessDenied"}}, "ListObjectVersions"),
    EndpointConnectionError(endpoint_url="https://unavailable.invalid"),
])
def test_unknown_history_never_falls_back_to_plain_delete(failure):
    s3 = Mock()
    s3.list_object_versions.side_effect = failure
    with pytest.raises(type(failure)):
        delete_exact_key(s3, bucket="b", key="exact")
    s3.delete_object.assert_not_called()


def test_exact_key_versions_markers_and_pagination_exclude_adjacent_keys():
    s3 = Mock()
    s3.head_object.side_effect = missing()
    s3.delete_objects.return_value = {}
    s3.list_object_versions.side_effect = [
        {"Versions": [{"Key": "exact", "VersionId": "v1", "Size": 42}, {"Key": "exact-adjacent", "VersionId": "never", "Size": 1000}],
         "IsTruncated": True, "NextKeyMarker": "exact", "NextVersionIdMarker": "v1"},
        {"DeleteMarkers": [{"Key": "exact", "VersionId": "marker"}]},
        {},
    ]
    result = delete_exact_key(s3, bucket="b", key="exact")
    assert result.versions_deleted == 2
    assert result.bytes_observed == 42
    deleted = [item for call in s3.delete_objects.call_args_list for item in call.kwargs["Delete"]["Objects"]]
    assert deleted == [{"Key": "exact", "VersionId": "v1"}, {"Key": "exact", "VersionId": "marker"}]
    assert s3.list_object_versions.call_args_list[1].kwargs["VersionIdMarker"] == "v1"


def test_per_key_delete_error_is_failure_even_with_http_200():
    s3 = Mock()
    s3.list_object_versions.return_value = {"Versions": [{"Key": "exact", "VersionId": "v1"}]}
    s3.delete_objects.return_value = {"Errors": [{"Code": "AccessDenied", "Message": "private detail"}]}
    with pytest.raises(CapabilityError, match="storage_version_delete_failed") as exc:
        delete_exact_key(s3, bucket="b", key="exact")
    assert "private detail" not in str(exc.value)


def test_late_write_and_retained_versions_prevent_quota_release_evidence():
    s3 = Mock()
    s3.delete_objects.return_value = {}
    s3.list_object_versions.side_effect = [{}, {"Versions": [{"Key": "exact", "VersionId": "late"}]}]
    with pytest.raises(CapabilityError, match="still_present"):
        delete_exact_key(s3, bucket="b", key="exact")


@pytest.mark.parametrize("prefix", ["", "/", "staging/", "owned-without-slash"])
def test_prefix_cleanup_cannot_delete_an_adjacent_directory(prefix):
    with pytest.raises(CapabilityError, match="owned_prefix"):
        delete_owned_prefix(Mock(), bucket="b", prefix=prefix)


def test_unsupported_inspection_is_not_tombstone_absence():
    s3 = Mock()
    s3.list_object_versions.side_effect = ClientError({"Error": {"Code": "NotImplemented"}}, "ListObjectVersions")
    with pytest.raises(ClientError):
        assert_exact_absent(s3, bucket="b", key="expired")
