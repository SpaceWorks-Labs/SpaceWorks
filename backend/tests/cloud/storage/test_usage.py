from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError

from apps.storage_capabilities import accounting
from apps.storage_capabilities.contracts import CapabilityError
from tests.cloud.storage.test_contracts import contract


def client_for(monkeypatch, value):
    monkeypatch.setattr(accounting, "capabilities_for", lambda *args, **kwargs: value)
    monkeypatch.setattr(accounting, "client_identity", lambda *args: value.identity)
    return Mock()


def test_incremental_current_bytes_include_private_staging_and_no_false_total(monkeypatch):
    s3 = client_for(monkeypatch, contract())
    s3.list_objects_v2.side_effect = [
        {"Contents": [{"Key": "staging/private", "Size": 10}], "IsTruncated": True, "NextContinuationToken": "page-2"},
        {"Contents": [{"Key": "final", "Size": 20}]},
    ]
    first = accounting.usage_page(s3, bucket="private", page_size=1)
    assert first.bytes_observed == 10 and first.continuation is not None
    second = accounting.usage_page(s3, bucket="private", cursor=first.continuation)
    assert second.bytes_observed == 20 and second.continuation is None
    assert s3.list_objects_v2.call_args.kwargs["ContinuationToken"] == "page-2"
    assert first.coverage == "current_objects"


def test_versioned_usage_counts_old_bytes_and_delete_markers(monkeypatch):
    s3 = client_for(monkeypatch, contract(versioning="suspended", list_delete_versions=True))
    s3.list_object_versions.return_value = {"Versions": [{"Size": 10}, {"Size": 20}], "DeleteMarkers": [{"Key": "old"}]}
    result = accounting.usage_page(s3, bucket="private")
    assert result.bytes_observed == 30
    assert result.delete_markers_observed == 1
    assert result.coverage == "retained_versions"


def test_changed_config_cannot_resume_old_inventory(monkeypatch):
    s3 = client_for(monkeypatch, contract(generation=2))
    with pytest.raises(CapabilityError, match="cursor_invalid"):
        accounting.usage_page(s3, bucket="private", cursor={"identity": "old", "configuration": "old", "token": "page-2"})
    s3.list_objects_v2.assert_not_called()


def test_unknown_usage_is_not_a_zero_observation(monkeypatch):
    s3 = client_for(monkeypatch, contract())
    s3.list_objects_v2.side_effect = ClientError({"Error": {"Code": "AccessDenied"}}, "ListObjectsV2")
    with pytest.raises(CapabilityError, match="usage_unknown"):
        accounting.usage_page(s3, bucket="private")


def test_truncated_response_without_token_is_not_complete(monkeypatch):
    s3 = client_for(monkeypatch, contract())
    s3.list_objects_v2.return_value = {"IsTruncated": True}
    with pytest.raises(CapabilityError, match="pagination_invalid"):
        accounting.usage_page(s3, bucket="private")
