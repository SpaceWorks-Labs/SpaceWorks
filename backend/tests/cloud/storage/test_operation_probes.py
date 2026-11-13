from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError

from apps.storage_capabilities import operation_probes
from apps.storage_capabilities.contracts import CapabilityError
from apps.storage_capabilities.cors import cors_rules
from tests.cloud.storage.test_contracts import contract


def test_failed_multipart_is_aborted_and_exact_probe_key_cleaned(monkeypatch):
    s3 = Mock()
    s3.create_multipart_upload.return_value = {"UploadId": "owned-upload"}
    s3.upload_part.side_effect = ClientError({"Error": {"Code": "ServiceUnavailable"}}, "UploadPart")
    deleted = Mock()
    monkeypatch.setattr(operation_probes, "delete_exact_key", deleted)
    with pytest.raises(CapabilityError, match="unknown"):
        operation_probes.probe_object_operations(s3, contract(copy=False, multipart=True))
    assert s3.abort_multipart_upload.call_args.kwargs["UploadId"] == "owned-upload"
    assert deleted.call_count == 1
    assert deleted.call_args.kwargs["key"].endswith("/multipart")


def test_object_lock_requires_retention_readback_and_delete_denial(monkeypatch):
    now = datetime(2026, 10, 18, tzinfo=UTC)
    monkeypatch.setattr(operation_probes.timezone, "now", lambda: now)
    audit = Mock()
    monkeypatch.setattr("apps.audit.services.record", audit)
    s3 = Mock()
    s3.put_object.return_value = {"VersionId": "locked-version"}
    from datetime import timedelta
    s3.get_object_retention.return_value = {"Retention": {"Mode": "COMPLIANCE", "RetainUntilDate": now + timedelta(seconds=60)}}
    s3.delete_object.side_effect = ClientError({"Error": {"Code": "AccessDenied"}}, "DeleteObject")
    result = operation_probes.probe_object_lock(s3, contract(versioning="enabled", list_delete_versions=True,
                                                           object_lock=True), mode="COMPLIANCE")
    assert result["object_lock"] is True
    assert result["lock_probe_version"] == "locked-version"
    assert audit.call_args.args[1] == "storage.object_lock_probe_requested"
    s3.head_object.assert_called_once()


def test_evidence_bucket_is_not_silently_made_a_worm_sink():
    s3 = Mock()
    with pytest.raises(CapabilityError, match="unavailable"):
        operation_probes.probe_object_lock(s3, contract(), mode="COMPLIANCE")
    s3.put_object.assert_not_called()


def test_manual_cors_rules_are_exact_and_include_required_headers():
    result = cors_rules(["https://space.example", "https://space.example"], {"put", "post"})
    rule = result["CORSRules"][0]
    assert rule["AllowedOrigins"] == ["https://space.example"]
    assert rule["AllowedMethods"] == ["GET", "HEAD", "PUT", "POST"]
    assert "If-None-Match" in rule["AllowedHeaders"]
    assert "x-amz-version-id" in rule["ExposeHeaders"]


@pytest.mark.parametrize("origin", ["*", "https://*.example", "https://example/path", "https://user:secret@example"])
def test_manual_cors_never_broadens_origin(origin):
    with pytest.raises(CapabilityError):
        cors_rules([origin], {"put"})
