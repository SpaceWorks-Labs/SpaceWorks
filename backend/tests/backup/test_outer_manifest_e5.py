"""The signed v2 deployment manifest: one platform-readable component (P1b)."""

from pathlib import Path
from types import SimpleNamespace
import json
import uuid

import pytest
from django.utils import timezone

from apps.backup import outer_manifest
from apps.backup.build_errors import BackupBuildError


pytestmark = pytest.mark.django_db


def _capture(capture_id, *makerspace_ids):
    return SimpleNamespace(
        capture_id=capture_id,
        population_ids=tuple(makerspace_ids),
        expected_main_ledger={"catalog": "verified"},
        source_catalog_digest="a" * 64,
        platform_recipients=frozenset({f"age1plat{uuid.uuid4().hex}"}),
    )


def _detailed(secret_object_key):
    return {
        "format": "spaceworks-phase5a-v3",
        "snapshot_at": timezone.now().isoformat(),
        "build": {"git_sha": "e5-build", "source_hash": "e5-source"},
        "oci_digest": "sha256:" + "e" * 64,
        "postgres": {
            "source_server_major": 16,
            "client": "pg_dump (PostgreSQL) 16.10",
            "supported_source_majors": [14, 15, 16, 17],
        },
        "storage": {"objects": [{"bucket_kind": "private", "key": secret_object_key}]},
        "contents": [{"path": "database.dump", "size": 13, "sha256": "f" * 64}],
    }


def _build(tmp_path, *makerspace_ids, detailed=None):
    Path(tmp_path, "database.dump").write_bytes(b"readable main")
    return outer_manifest.build_outer_manifest(
        archive=SimpleNamespace(pk=uuid.uuid4()),
        capture=_capture(uuid.uuid4(), *makerspace_ids),
        detailed_manifest=detailed or _detailed("ordinary-object-key"),
        root=tmp_path,
    )


def test_manifest_is_an_allowlist_with_exactly_one_signed_component(tmp_path):
    raw_object_key = "raw-low-entropy-object-key-e5"
    detailed = _detailed(raw_object_key)
    detailed["tenant_name"] = "tenant-plaintext-e5"

    manifest = _build(tmp_path, 41, 42, detailed=detailed)
    encoded = json.dumps(manifest, sort_keys=True).encode()

    assert set(manifest) == {
        "format", "protocol_version", "artifact_id", "capture_id",
        "source_timestamp", "build_identity", "postgres", "makerspace_ids",
        "main_component", "object_ledgers", "content_ledgers", "archive_signature",
        "archive_id", "scope", "age_encrypted", "snapshot_at", "build",
        "oci_digest", "covered_makerspace_ids", "excluded_makerspace_ids",
        "partial", "recipient_fingerprints", "contents",
    }
    for forbidden in (raw_object_key, "tenant-plaintext-e5"):
        assert forbidden.encode() not in encoded
    assert manifest["protocol_version"] == "spaceworks-lane-e-b1-v2"
    assert manifest["makerspace_ids"] == manifest["covered_makerspace_ids"] == [41, 42]
    assert manifest["excluded_makerspace_ids"] == [] and manifest["partial"] is False
    assert manifest["main_component"]["path"] == "database.dump"
    assert len(manifest["main_component"]["recipient_fingerprints"]) == 1
    assert "public_key" not in manifest["archive_signature"]
    assert outer_manifest.verify_outer_manifest(manifest) is True

    tampered = {**manifest, "postgres": {**manifest["postgres"], "source_server_major": 17}}
    with pytest.raises(BackupBuildError, match="signature is invalid"):
        outer_manifest.verify_outer_manifest(tampered)


@pytest.mark.parametrize("postgres_major", (None, True, 0, 9, 100, "16"))
def test_manifest_rejects_missing_mistyped_or_implausible_postgres_major(
    tmp_path, postgres_major
):
    manifest = _build(tmp_path, 41)
    manifest.pop("archive_signature")
    if postgres_major is None:
        manifest.pop("postgres")
    else:
        manifest["postgres"] = {**manifest["postgres"], "source_server_major": postgres_major}
    with pytest.raises(BackupBuildError, match="structure is invalid"):
        outer_manifest.validate_unsigned_manifest(
            manifest, protocol_version=outer_manifest.PROTOCOL_VERSION
        )


def test_manifest_rejects_missing_source_build_identity(tmp_path):
    manifest = _build(tmp_path, 41)
    manifest.pop("archive_signature")
    manifest["build_identity"] = {**manifest["build_identity"], "build": {"git_sha": "x"}}
    with pytest.raises(BackupBuildError, match="structure is invalid"):
        outer_manifest.validate_unsigned_manifest(
            manifest, protocol_version=outer_manifest.PROTOCOL_VERSION
        )


@pytest.mark.parametrize("makerspace_id", (0, -3))
def test_manifest_rejects_non_positive_makerspace_identity(tmp_path, makerspace_id):
    with pytest.raises(BackupBuildError, match="structure is invalid"):
        _build(tmp_path, makerspace_id)


def test_a_v1_protocol_manifest_no_longer_validates(tmp_path):
    manifest = _build(tmp_path, 41)
    manifest.pop("archive_signature")
    manifest["protocol_version"] = "spaceworks-lane-e-b1-v1"
    with pytest.raises(BackupBuildError, match="structure is invalid"):
        outer_manifest.validate_unsigned_manifest(
            manifest, protocol_version=outer_manifest.PROTOCOL_VERSION
        )


def test_component_ids_bind_capture_and_kind():
    first, second = uuid.uuid4(), uuid.uuid4()
    assert len({
        outer_manifest.component_id(first, "main"),
        outer_manifest.component_id(second, "main"),
    }) == 2
