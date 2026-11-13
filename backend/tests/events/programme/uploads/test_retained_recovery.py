"""Real source/recovery gates around cleanup; fake storage only at the I/O edge."""
from datetime import timedelta
from uuid import uuid4

import pytest
from django.db import connection, transaction
from django.utils import timezone

from apps.backup.models import DeploymentRecoveryState
from apps.events.submissions.models_assets import EventAssetObligation, SubmissionAssetWork, EventAssetUsage
from apps.events.submissions.obligations import reconcile
from apps.events.submissions.retention_jobs import cleanup_asset
from apps.events.submissions.storage import EventAssetStorage
from apps.events.tasks_retention import _retention_event
from apps.makerspaces.storage_events_programme import EventAssetStoragePool
from apps.tenant_migration.gate_runtime import boundary_tenant_write
from apps.tenant_migration.gate_errors import SourceMigrationGateClosed
from apps.tenant_migration.models_source_gate import SourceMigrationGate
from tests.events.programme.uploads.fake_storage import FakeS3
from tests.events.programme.uploads.test_pool_receipts import asset_fixture

pytestmark = pytest.mark.django_db(transaction=True)


def freeze(space):
    SourceMigrationGate.objects.update_or_create(makerspace=space, defaults={
        "state": "migrated_out", "owner_id": uuid4(), "heartbeat_at": timezone.now(),
        "lease_expires_at": timezone.now()+timedelta(hours=1),
    })


def normal():
    DeploymentRecoveryState.objects.update_or_create(pk=1, defaults={"mode": "normal"})


def test_expired_bytes_clean_under_source_freeze_but_normal_workflows_still_refuse():
    normal()
    event, asset = asset_fixture("retained-source")
    asset.state, asset.expired_at = "aborted", timezone.now()
    asset.save(update_fields=["state", "expired_at"])
    EventAssetUsage.objects.create(event=event, reserved_bytes=80)
    SubmissionAssetWork.objects.create(participant_asset=asset)
    with transaction.atomic():
        EventAssetStoragePool().apply_locked(event=event, asset_uuid=asset.public_id, operation="reserve", bytes=80)
    fake = FakeS3()
    for key in (asset.object_key, asset.staging_key, asset.verification_key):
        fake.put_object(Bucket="private", Key=key, Body=b"owned")
    freeze(event.makerspace)
    with pytest.raises(SourceMigrationGateClosed), boundary_tenant_write(event.makerspace_id):
        pytest.fail("Normal workflow acquired cleanup authority")
    assert cleanup_asset(asset_id=asset.pk, participant=True, storage=EventAssetStorage(fake, fake, "private"))
    asset.refresh_from_db()
    assert asset.deleted_at is not None and asset.reserved_bytes == 0
    assert EventAssetUsage.objects.get(event=event).reserved_bytes == 0
    assert all(not fake.objects[key] for key in (asset.object_key, asset.staging_key, asset.verification_key))
    with pytest.raises(SourceMigrationGateClosed), boundary_tenant_write(event.makerspace_id):
        pytest.fail("Cleanup leaked a generic bypass")


def test_purged_row_obligation_catches_late_versions_and_multipart_without_tenant_workflow():
    normal()
    event, asset = asset_fixture("purged-custody")
    with transaction.atomic():
        EventAssetStoragePool().apply_locked(event=event, asset_uuid=asset.public_id, operation="reserve", bytes=80)
    receipt = EventAssetObligation.objects.get(asset_uuid=asset.public_id)
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SET LOCAL app.allow_immutable_delete='on'")
        cursor.execute("DELETE FROM events_hackathonparticipantasset WHERE id=%s", [asset.pk])
    freeze(event.makerspace)
    fake = FakeS3()
    fake.put_object(Bucket="private", Key=asset.staging_key, Body=b"late")
    fake.create_multipart_upload(Bucket="private", Key=asset.staging_key)
    storage = EventAssetStorage(fake, fake, "private")
    assert reconcile(receipt.pk, storage=storage)
    receipt.refresh_from_db()
    assert receipt.fully_released and receipt.reserved_bytes == 0 and not fake.multipart
    # The permanent record repeats strict deletion instead of forgetting the key.
    fake.put_object(Bucket="private", Key=asset.staging_key, Body=b"very late")
    EventAssetObligation.objects.filter(pk=receipt.pk).update(next_attempt_at=timezone.now())
    assert reconcile(receipt.pk, storage=storage)
    assert not fake.objects[asset.staging_key]


def test_recovery_quarantine_refuses_before_storage_or_expiry_state_changes():
    normal()
    event, asset = asset_fixture("quarantined-retention")
    DeploymentRecoveryState.objects.filter(pk=1).update(mode="quarantined")
    try:
        with pytest.raises(RuntimeError), _retention_event(event.pk):
            pytest.fail("Quarantine admitted retention")
    finally:
        DeploymentRecoveryState.objects.filter(pk=1).update(mode="normal")
    asset.refresh_from_db()
    assert asset.state == "reserved" and asset.expired_at is None
