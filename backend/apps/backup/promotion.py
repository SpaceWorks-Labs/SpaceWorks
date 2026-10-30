"""The single no-I/O transaction that makes a deployment artifact available."""

import uuid

from django.db import transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.backup.artifact_ledger import ArtifactLedgerMismatch
from apps.backup.retention import archive_expires_at
from apps.backup.models import (
    BackupArchive,
    BackupArtifactComponent,
    BackupArtifactLedger,
    PlatformBackupSettings,
)
from apps.backup.promotion_validation import (
    validate_artifact_rows,
    validate_frozen_state,
)


PROMOTION_LOCK_ORDER = (
    "artifacts",
    "components",
    "archive",
    "platform_settings",
)


def promote_verified_artifact(artifact_id):
    facts = BackupArtifactLedger.objects.values(
        "artifact_id", "predecessor_artifact_id_snapshot"
    ).get(pk=artifact_id)
    artifact_ids = tuple(sorted(
        {
            facts["artifact_id"],
            *(
                (facts["predecessor_artifact_id_snapshot"],)
                if facts["predecessor_artifact_id_snapshot"] else ()
            ),
        },
        key=str,
    ))
    return _promote_atomic(artifact_id, artifact_ids)


@transaction.atomic
def _promote_atomic(artifact_id, artifact_ids):
    artifacts = _lock_artifacts(artifact_ids)
    artifact = artifacts.get(uuid.UUID(str(artifact_id)))
    if artifact is None:
        raise ArtifactLedgerMismatch("The durable artifact disappeared before promotion.")
    components = _lock_components(artifact)
    archive = BackupArchive.objects.select_for_update().get(
        pk=artifact.archive_uuid_snapshot
    )
    # Singleton, created on demand everywhere else via load(). Promotion must not
    # be the one caller that assumes some earlier code path already made the row:
    # a bare get() would abort an otherwise-valid promotion inside the
    # transaction, after all the capture work is already done.
    PlatformBackupSettings.load()
    settings_row = PlatformBackupSettings.objects.select_for_update().get(pk=1)

    if artifact.state in {
        BackupArtifactLedger.State.AVAILABLE,
        BackupArtifactLedger.State.SUPERSEDED,
        BackupArtifactLedger.State.BYTES_DELETED,
    }:
        return archive
    if artifact.state != BackupArtifactLedger.State.FINAL_VERIFIED:
        raise ArtifactLedgerMismatch("Only a stream-verified final artifact can be promoted.")
    if (
        artifact.final_verified_size_bytes != artifact.expected_size_bytes
        or artifact.final_verified_sha256 != artifact.outer_sha256
    ):
        raise ArtifactLedgerMismatch("The verified final storage facts changed.")
    _enter_promotion_state(archive)
    validate_frozen_state(artifact, settings_row, artifacts)
    validate_artifact_rows(artifact, archive, components)

    now = timezone.now()

    BackupArtifactComponent.objects.filter(artifact=artifact).update(
        storage_state=BackupArtifactComponent.StorageState.AVAILABLE,
        available_at=now,
    )
    artifact.state = BackupArtifactLedger.State.AVAILABLE
    artifact.promoted_at = now
    artifact.cleanup_pending = True
    artifact.save(update_fields=("state", "promoted_at", "cleanup_pending"))
    predecessor_id = artifact.predecessor_artifact_id_snapshot
    if predecessor_id:
        predecessor = artifacts[predecessor_id]
        if predecessor.state == BackupArtifactLedger.State.AVAILABLE:
            predecessor.state = BackupArtifactLedger.State.SUPERSEDED
            predecessor.superseded_at = now
            predecessor.save(update_fields=("state", "superseded_at"))

    archive.status = BackupArchive.Status.AVAILABLE
    archive.object_key = artifact.final_locator
    archive.manifest = artifact.outer_manifest
    archive.size_bytes = artifact.expected_size_bytes
    archive.archive_sha256 = artifact.outer_sha256
    archive.age_encrypted = True
    archive.completed_at = now
    archive.failure_detail = ""
    if archive.expires_at is None:
        archive.expires_at = archive_expires_at(archive, now, settings_row.retention_days)
    archive.save(update_fields=(
        "status", "object_key", "manifest", "size_bytes", "archive_sha256",
        "age_encrypted", "completed_at", "expires_at", "failure_detail", "updated_at",
    ))
    audit.record(
        archive.requested_by,
        "backup.archive_completed",
        target=archive,
        meta={
            "scope": archive.scope,
            "size_bytes": artifact.expected_size_bytes,
        },
    )
    if archive.backup_run_id is None:
        settings_row.last_success_at = now
        settings_row.last_error = ""
        settings_row.save(
            update_fields=("last_success_at", "last_error", "updated_at")
        )
    return archive


def _enter_promotion_state(archive):
    if archive.status == BackupArchive.Status.RUNNING:
        archive.status = BackupArchive.Status.PROMOTING
        archive.save(update_fields=("status", "updated_at"))
    elif archive.status != BackupArchive.Status.PROMOTING:
        raise ArtifactLedgerMismatch("The archive is not owned for promotion.")


def _lock_artifacts(artifact_ids):
    return {
        row.artifact_id: row
        for row in BackupArtifactLedger.objects.select_for_update().filter(
            artifact_id__in=artifact_ids
        ).order_by("artifact_id")
    }


def _lock_components(artifact):
    return tuple(
        BackupArtifactComponent.objects.select_for_update().filter(
            artifact=artifact
        ).order_by("pk")
    )
