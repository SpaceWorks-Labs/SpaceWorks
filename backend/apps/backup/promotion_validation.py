"""Fail-closed equality checks performed under the promotion locks."""

import hmac

from apps.backup.artifact_ledger import ArtifactLedgerMismatch, component_specs
from apps.backup.models import BackupArchive, BackupArtifactLedger
from apps.backup.outer_manifest import manifest_digest, verify_outer_manifest


def validate_frozen_state(artifact, settings_row, artifacts):
    snapshot = artifact.frozen_promotion_snapshot["retained"]
    expected_ids = [item["makerspace_id"] for item in snapshot]
    if expected_ids != artifact.outer_manifest["makerspace_ids"]:
        raise ArtifactLedgerMismatch(
            "The signed manifest and frozen makerspace population differ."
        )
    if settings_row.last_success_at != artifact.predecessor_success_at_snapshot:
        raise ArtifactLedgerMismatch("The predecessor backup success state changed.")
    predecessor_id = artifact.predecessor_artifact_id_snapshot
    if predecessor_id and (
        predecessor_id not in artifacts
        or artifacts[predecessor_id].state != BackupArtifactLedger.State.AVAILABLE
    ):
        raise ArtifactLedgerMismatch("The predecessor artifact state changed.")


def validate_artifact_rows(artifact, archive, components):
    manifest = artifact.outer_manifest
    verify_outer_manifest(manifest)
    if (
        manifest["artifact_id"] != str(artifact.artifact_id)
        or manifest["capture_id"] != str(artifact.capture_id)
        or manifest["format"] != artifact.format
        or manifest_digest(manifest) != artifact.outer_manifest_sha256
        or archive.pk != artifact.archive_uuid_snapshot
        or archive.status != BackupArchive.Status.PROMOTING
        or manifest.get("backup_run_id")
        != (str(archive.backup_run_id) if archive.backup_run_id else None)
    ):
        raise ArtifactLedgerMismatch("The artifact or archive identity changed.")
    if archive.backup_run_id is not None:
        cohort = {str(key) for key in archive.backup_run.flag_snapshot}
        if not cohort <= {str(value) for value in manifest["makerspace_ids"]}:
            raise ArtifactLedgerMismatch(
                "The backup run cohort is not covered by the signed population."
            )
    expected = component_specs(manifest)
    actual = {str(item.component_id): item for item in components}
    if set(actual) != {str(item["component_id"]) for item in expected}:
        raise ArtifactLedgerMismatch("The durable component set changed.")
    for item in expected:
        row = actual[str(item["component_id"])]
        if (
            row.kind != item["kind"]
            or row.makerspace_id_snapshot != item["makerspace_id_snapshot"]
            or row.ciphertext_path != item["ciphertext_path"]
            or row.size_bytes != item["size_bytes"]
            or not hmac.compare_digest(row.ciphertext_sha256, item["ciphertext_sha256"])
        ):
            raise ArtifactLedgerMismatch("A durable component fact changed.")
