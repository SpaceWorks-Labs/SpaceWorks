from datetime import datetime, timedelta, timezone

import pytest

from apps.backup.object_reference_retention import (
    ADAPTERS, event_asset_projection, evidence_projection,
)
from apps.backup.build_errors import BackupBuildError

NOW = datetime(2026, 10, 18, tzinfo=timezone.utc)


def row(**changes):
    return {"state": "ready", "expires_at": NOW + timedelta(days=1),
            "expired_at": None, "expired_size_bytes": 0, "actual_bytes": 123, "sha256": "a" * 64, **changes}


@pytest.mark.parametrize("label", ["events.SubmissionAsset", "events.HackathonParticipantAsset"])
def test_direct_asset_fields_and_live_projection(label):
    adapter = ADAPTERS[label, "object_key"]
    assert not any("object_retention_state" in field for field in adapter.query_fields)
    assert adapter.project(row(), NOW).retention_state == "live"


def test_expired_bytes_are_expected_absence():
    projected = event_asset_projection(row(state="expired", expired_at=NOW, expired_size_bytes=123), NOW)
    assert projected.retention_state == "expired"
    assert projected.expired_size_bytes == 123


@pytest.mark.parametrize("changes", [
    {"state": "expired"}, {"state": "copying"}, {"state": "expiring"},
    {"expires_at": NOW}, {"expired_at": NOW}, {"actual_bytes": 0}, {"state": "unknown"},
])
def test_capture_refuses_inconsistent_or_inflight_assets(changes):
    with pytest.raises(BackupBuildError):
        event_asset_projection(row(**changes), NOW)


def test_mutable_staging_is_not_canonical_content():
    assert not event_asset_projection(row(state="uploading"), NOW).capture


def test_canonical_proof_rejects_capture_with_wrong_size_or_hash():
    from apps.backup.object_capture_proof import assert_capture_proof
    expected = {"expected_size_bytes": 123, "expected_sha256": "a" * 64}
    assert_capture_proof(expected, {"size": 123, "sha256": "a" * 64})
    for capture in ({"size": 122, "sha256": "a" * 64}, {"size": 123, "sha256": "b" * 64}):
        with pytest.raises(BackupBuildError):
            assert_capture_proof(expected, capture)


def test_evidence_projection_keeps_shipped_relation_contract():
    assert evidence_projection({}, NOW).retention_state == "live"
    projected = evidence_projection({"object_retention_state__status": "expired",
        "object_retention_state__object_expired_at": NOW,
        "object_retention_state__expired_size_bytes": 17}, NOW)
    assert projected.expired_size_bytes == 17
    with pytest.raises(BackupBuildError):
        evidence_projection({"object_retention_state__status": "expiring"}, NOW)
