"""Independent expiry respects live leases, attachment fences and tenant admission."""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock
import uuid

import pytest
from django.db import transaction, connection, connections
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.evidence import finalization, services_upload, storage
from apps.evidence.models import EvidencePhoto, EvidenceUploadFinalization, EvidenceObjectRetentionState
from apps.makerspaces.models import Makerspace, StorageQuotaReservation
from apps.makerspaces.storage_reservation_cleanup import cleanup, sweep
from apps.makerspaces.storage_reservations import reserved_bytes
from apps.space_controls.models import SpaceControlState
from apps.tenant_migration.models_source_gate import SourceMigrationGate
from tests.return_helpers import make_member, make_space

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_inventory, pytest.mark.area_lending]


def world(settings, monkeypatch):
    settings.EVIDENCE_OBJECT_EXPIRY_ENABLED = False
    settings.EVIDENCE_ABANDONED_UPLOAD_CLEANUP_ENABLED = False
    space = make_space("r1-cleanup-leases")
    actor = make_member("r1-cleanup-owner", space)
    photo, _ = services_upload.issue_upload(space, actor=actor, evidence_type="return", size_bytes=10,
        content_type="image/png", consumption_state="unconsumed",
        presigner=Mock(return_value={"url": "https://upload.test"}))
    now = timezone.now()
    receipt = StorageQuotaReservation.objects.get(object_key=photo.object_key)
    StorageQuotaReservation.objects.filter(pk=receipt.pk).update(expires_at=now - timedelta(seconds=1))
    EvidenceUploadFinalization.objects.create(evidence=photo, status="promoting", claim_token=uuid.uuid4())
    monkeypatch.setattr(storage, "_client", lambda: object())
    deletion = Mock(return_value=SimpleNamespace(absence_confirmed=True))
    monkeypatch.setattr("apps.object_storage.delete_all_versions", deletion)
    return space, photo, receipt, deletion, now


def test_fresh_promotion_keeps_all_debt_and_never_deletes(settings, monkeypatch):
    space, photo, receipt, deletion, now = world(settings, monkeypatch)
    assert cleanup(receipt.pk, now=now) is False
    deletion.assert_not_called()
    assert reserved_bytes(space) == 10
    assert EvidenceUploadFinalization.objects.get(evidence=photo).status == "promoting"
    assert EvidenceObjectRetentionState.objects.filter(evidence=photo).count() == 0
    assert AuditLog.objects.filter(makerspace=space, action="storage.upload_reservation_released").count() == 0


def test_expired_promotion_is_fenced_even_if_the_old_worker_completes_late(settings, monkeypatch):
    space, photo, receipt, deletion, now = world(settings, monkeypatch)
    lease = max(settings.EVIDENCE_URL_TTL_SECONDS, 60)
    EvidenceUploadFinalization.objects.filter(evidence=photo).update(updated_at=now - timedelta(seconds=lease))
    assert cleanup(receipt.pk, now=now) is True
    assert {call.kwargs["key"] for call in deletion.call_args_list} == {receipt.object_key, receipt.staging_key}
    assert (reserved_bytes(space), Makerspace.objects.get(pk=space.pk).storage_bytes_used) == (0, 0)
    assert EvidencePhoto.objects.filter(pk=photo.pk, consumption_state="unconsumed").count() == 1
    assert EvidenceObjectRetentionState.objects.get(evidence=photo).status == "expired"
    # Simulate a crashed worker returning after the cleanup commit. Its result
    # cannot reopen attachment; subsequent late bytes remain receipt-owned.
    finalization._complete(photo.pk, storage.EvidenceValidationResult(10, "image/png"))
    with transaction.atomic():
        assert finalization.lock_evidence_for_attachment(photo.pk) is False
    with pytest.raises(storage.EvidenceObjectValidationError) as refused:
        finalization._claim(photo.pk)
    assert refused.value.code == "expired"
    assert cleanup(receipt.pk, now=now + timedelta(hours=7)) is True
    assert deletion.call_count == 4
    assert AuditLog.objects.filter(makerspace=space, action="storage.upload_reservation_released").count() == 1


def test_unconfirmed_expired_promotion_deletion_keeps_the_debt(settings, monkeypatch):
    space, photo, receipt, deletion, now = world(settings, monkeypatch)
    EvidenceUploadFinalization.objects.filter(evidence=photo).update(updated_at=now - timedelta(days=1))
    deletion.return_value = SimpleNamespace(absence_confirmed=False)
    with pytest.raises(storage.StorageUnavailable):
        cleanup(receipt.pk, now=now)
    assert reserved_bytes(space) == 10
    assert StorageQuotaReservation.objects.get(pk=receipt.pk).released is False
    assert AuditLog.objects.filter(makerspace=space, action="storage.upload_reservation_released").count() == 0


@pytest.mark.parametrize("mode,expected", [("read_only", 1), ("suspended", 0), ("migrated_out", 0)])
def test_sweep_uses_retention_admission_and_keeps_suspension_and_source_fences(mode, expected, settings, monkeypatch):
    space, photo, receipt, deletion, now = world(settings, monkeypatch)
    EvidenceUploadFinalization.objects.filter(evidence=photo).update(status="pending", claim_token=None)
    if mode == "read_only":
        SpaceControlState.objects.update_or_create(makerspace=space,
            defaults={"read_only_at": now, "read_only_source": "manual"})
    elif mode == "suspended":
        Makerspace.objects.filter(pk=space.pk).update(lifecycle_state="suspended")
    else:
        SourceMigrationGate.objects.update_or_create(makerspace=space, defaults={"state": "migrated_out",
            "owner_id": uuid.uuid4(), "heartbeat_at": now, "lease_expires_at": now + timedelta(hours=1)})
    assert sweep() == expected
    receipt.refresh_from_db()
    assert receipt.released is bool(expected)
    assert reserved_bytes(space) == (0 if expected else 10)
    assert deletion.call_count == expected * 2
    assert AuditLog.objects.filter(makerspace=space, action="storage.upload_reservation_released").count() == expected


def test_late_completer_waits_for_expiry_and_cannot_reopen_attachment(settings, monkeypatch):
    from conftest import _BoundedThreadPoolExecutor as ThreadPoolExecutor
    from threading import Event
    from django.db import close_old_connections, connection
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    space, photo, receipt, deletion, now = world(settings, monkeypatch)
    EvidenceUploadFinalization.objects.filter(evidence=photo).update(updated_at=now - timedelta(days=1))
    deleting, release, completing = Event(), Event(), Event()
    def delete(*args, **kwargs):
        deleting.set()
        assert release.wait(10)
        return SimpleNamespace(absence_confirmed=True)
    deletion.side_effect = delete
    def expire():
        close_old_connections()
        try:
            if connection.vendor == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '5s'")
            return cleanup(receipt.pk, now=now)
        finally:
            connections.close_all()
    def complete():
        close_old_connections()
        try:
            if connection.vendor == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '5s'")
            completing.set()
            return finalization._complete(photo.pk, storage.EvidenceValidationResult(10, "image/png"))
        finally:
            connections.close_all()
    with ThreadPoolExecutor(max_workers=2) as pool:
        expiry = pool.submit(expire)
        assert deleting.wait(10)
        late = pool.submit(complete)
        try:
            assert completing.wait(10)
        finally:
            release.set()
        assert expiry.result(timeout=15) is True
        assert late.result(timeout=15).size == 10
    with transaction.atomic():
        assert finalization.lock_evidence_for_attachment(photo.pk) is False
    assert EvidenceObjectRetentionState.objects.get(evidence=photo).status == "expired"
    assert reserved_bytes(space) == 0
    assert AuditLog.objects.filter(makerspace=space, action="storage.upload_reservation_released").count() == 1
