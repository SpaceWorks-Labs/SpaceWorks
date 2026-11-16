"""The single no-I/O promotion transaction for a one-component deployment artifact."""

from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
import uuid

import pytest
from django.utils import timezone

from apps.audit import services as audit_services
from apps.audit.models import AuditLog
from apps.backup import artifact_ledger, outer_manifest, promotion, reconciliation
from apps.backup.models import BackupArchive, BackupArtifactLedger, PlatformBackupSettings
from apps.makerspaces.models import Makerspace


pytestmark = pytest.mark.django_db(transaction=True)


def _prepared(tmp_path, *, population=None):
    space = Makerspace.objects.create(name="E5 space", slug=f"e5-{uuid.uuid4().hex}")
    archive = BackupArchive.objects.create(
        scope=BackupArchive.Scope.DEPLOYMENT,
        status=BackupArchive.Status.RUNNING,
        object_key=f"backup-archives/deployment/{uuid.uuid4()}.tar.age",
        expires_at=timezone.now() + timedelta(days=1),
    )
    capture = SimpleNamespace(
        capture_id=uuid.uuid4(),
        population_ids=(space.pk,),
        expected_main_ledger={"catalog": "verified"},
        source_catalog_digest="a" * 64,
        platform_recipients=frozenset({f"age1plat{uuid.uuid4().hex}"}),
    )
    Path(tmp_path, "database.dump").write_bytes(b"main")
    detailed = {
        "format": "spaceworks-phase5a-v3",
        "snapshot_at": timezone.now().isoformat(),
        "build": {"git_sha": "e5", "source_hash": "e5-source"},
        "oci_digest": "sha256:" + "a" * 64,
        "postgres": {
            "source_server_major": 16,
            "client": "pg_dump (PostgreSQL) 16.10",
            "supported_source_majors": [14, 15, 16, 17],
        },
        "storage": {"objects": []},
        "contents": [],
    }
    manifest = outer_manifest.build_outer_manifest(
        archive=archive, capture=capture, detailed_manifest=detailed, root=tmp_path
    )
    size, digest = 101, "e" * 64
    retained = population if population is not None else [space.pk]
    build = SimpleNamespace(
        manifest=manifest,
        promotion_snapshot={
            "predecessor_artifact_id": None,
            "predecessor_success_at": None,
            "retained": [{"makerspace_id": value} for value in retained],
        },
        archive_sha256=digest,
    )
    ledger = artifact_ledger.persist_pending(archive, build, size)
    return space, None, archive, ledger, size, digest


def _final_verified(tmp_path, **kwargs):
    values = _prepared(tmp_path, **kwargs)
    artifact_ledger.mark_final_verified(values[3].pk, values[4], values[5])
    return values


def test_promotion_commits_availability_audit_and_success_together(tmp_path):
    _space, _none, archive, ledger, _size, _digest = _final_verified(tmp_path)

    promotion.promote_verified_artifact(ledger.pk)

    archive.refresh_from_db()
    ledger.refresh_from_db()
    completed = AuditLog.objects.get(action="backup.archive_completed", target_id=str(archive.pk))
    assert archive.status == BackupArchive.Status.AVAILABLE
    assert ledger.state == BackupArtifactLedger.State.AVAILABLE
    assert set(completed.meta) == {"scope", "size_bytes"}
    assert PlatformBackupSettings.load().last_success_at == archive.completed_at


def test_promotion_rolls_back_every_success_write_when_completion_audit_fails(
    monkeypatch, tmp_path
):
    _space, _none, archive, ledger, _size, _digest = _final_verified(tmp_path)
    real_record = audit_services.record

    def fail_completed(actor, action, **kwargs):
        if action == "backup.archive_completed":
            raise RuntimeError("injected audit failure")
        return real_record(actor, action, **kwargs)

    monkeypatch.setattr(promotion.audit, "record", fail_completed)
    with pytest.raises(RuntimeError, match="audit failure"):
        promotion.promote_verified_artifact(ledger.pk)

    archive.refresh_from_db()
    ledger.refresh_from_db()
    assert archive.status == BackupArchive.Status.RUNNING
    assert ledger.state == BackupArtifactLedger.State.FINAL_VERIFIED
    assert PlatformBackupSettings.load().last_success_at is None


def test_promotion_refuses_a_frozen_population_that_differs_from_the_signed_one(tmp_path):
    _space, _none, archive, ledger, _size, _digest = _final_verified(
        tmp_path, population=[999_999]
    )
    with pytest.raises(artifact_ledger.ArtifactLedgerMismatch, match="population differ"):
        promotion.promote_verified_artifact(ledger.pk)
    archive.refresh_from_db()
    assert archive.status == BackupArchive.Status.RUNNING
    assert not AuditLog.objects.filter(action="backup.archive_completed").exists()


def test_pending_final_reconciliation_uses_the_shared_promotion_primitive(
    monkeypatch, tmp_path
):
    _space, _none, _archive, ledger, size, digest = _prepared(tmp_path)
    calls = []
    monkeypatch.setattr(
        reconciliation.storage, "object_exists", lambda key: key == ledger.final_locator,
    )
    monkeypatch.setattr(
        reconciliation.storage, "stream_verify", lambda *_args, **_kwargs: (size, digest)
    )
    monkeypatch.setattr(reconciliation.storage, "delete_archive", lambda _key: True)
    monkeypatch.setattr(
        reconciliation, "promote_verified_artifact", lambda artifact_id: calls.append(artifact_id)
    )

    reconciliation._reconcile_pending(ledger.pk)

    ledger.refresh_from_db()
    assert ledger.state == BackupArtifactLedger.State.FINAL_VERIFIED
    assert calls == [ledger.pk]


def test_repeated_pending_persistence_is_idempotent_with_one_component(tmp_path):
    _space, _none, archive, first, size, _digest = _prepared(tmp_path)
    build = SimpleNamespace(
        manifest=first.outer_manifest,
        promotion_snapshot=first.frozen_promotion_snapshot,
        archive_sha256=first.outer_sha256,
    )

    second = artifact_ledger.persist_pending(archive, build, size)

    assert second.pk == first.pk
    assert list(second.components.values_list("kind", flat=True)) == ["main"]


def test_runner_and_reconciler_share_the_declared_promotion_lock_order():
    assert reconciliation.promote_verified_artifact is promotion.promote_verified_artifact
    assert promotion.PROMOTION_LOCK_ORDER == (
        "artifacts", "components", "archive", "platform_settings",
    )
