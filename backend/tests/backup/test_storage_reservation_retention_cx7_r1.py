"""Reservation cleanup debt must never override canonical evidence tombstones."""

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.backup import archive_objects, storage as backup_storage
from apps.backup.object_ownership import MAIN_COMPONENT, build_object_ownership_plan
from apps.evidence import services_upload, storage
from apps.evidence.finalization import charge_storage_once
from apps.evidence.models import (
    EvidenceObjectRetentionState,
    EvidencePhoto,
    EvidenceUploadFinalization,
)
from apps.evidence.services_retention import sweep_evidence_retention
from apps.makerspaces.models import Makerspace, StorageQuotaReservation
from apps.makerspaces.storage_reservation_cleanup import cleanup


pytestmark = pytest.mark.django_db


@pytest.fixture
def upload(settings):
    settings.MANAGED_PLANS_ENABLED = False
    settings.STORAGE_PRESIGN_METHOD = "put"
    space = Makerspace.objects.create(
        name="Reservation backup", slug="reservation-backup",
        resource_limit_overrides={"storage": 1024},
    )
    actor = get_user_model().objects.create_user(
        username="reservation-backup", email="reservation-backup@example.test",
    )
    photo, _ = services_upload.issue_upload(
        space, actor=actor, evidence_type="issue", content_type="image/png",
        size_bytes=10, consumption_state="unconsumed",
        presigner=Mock(return_value={"url": "https://storage.test/upload"}),
    )
    reservation = StorageQuotaReservation.objects.get(object_key=photo.object_key)
    # No canonical row owns this original/normalized pair. Even unreleased debt
    # must neither enter the plan nor authorize archive byte capture.
    original = f"items/{space.pk}/reservation-only.png"
    StorageQuotaReservation.objects.create(
        makerspace=space, object_key=original, final_key=original + ".webp",
        staging_key="staging/" + original, bucket=settings.AWS_STORAGE_BUCKET_NAME,
        final_bucket=settings.PUBLIC_IMAGE_BUCKET,
        storage_endpoint=settings.AWS_S3_ENDPOINT_URL or "", kind="public_image",
        size_bytes=10, expires_at=timezone.now() + timedelta(hours=1),
    )
    return photo, reservation


def assert_expired_capture(photo, expected_size, tmp_path, monkeypatch, settings):
    state = EvidenceObjectRetentionState.objects.get(evidence=photo)
    assert state.status == "expired"
    assert state.expired_size_bytes == expected_size
    assert state.object_expired_at is not None
    assert EvidencePhoto.objects.filter(pk=photo.pk).count() == 1
    with CaptureQueriesContext(connection) as queries:
        plan = build_object_ownership_plan()
    assert [query["sql"] for query in queries
            if StorageQuotaReservation._meta.db_table in query["sql"]] == []
    assert len(plan.references) == 1
    assert plan.references[0].site == f"evidence.EvidencePhoto:{photo.pk}:object_key"
    ownership = {
        "canonical_component": MAIN_COMPONENT,
        "makerspace_id": photo.makerspace_id,
        "module_key": "",
        "retention_state": "expired",
        "object_expired_at": state.object_expired_at.isoformat(),
        "expired_size_bytes": expected_size,
    }
    closure = plan.closure(MAIN_COMPONENT)
    assert closure == {"private": {photo.object_key: ownership}, "public_image": {}}
    absence = Mock()
    download = Mock(side_effect=AssertionError("Expired evidence attempted byte capture"))
    monkeypatch.setattr(backup_storage, "assert_object_absent", absence)
    monkeypatch.setattr(backup_storage, "download_object", download)

    manifest = archive_objects.capture_objects(
        tmp_path, closure, {"private": "versioned", "public_image": "versioned"},
    )

    assert [call.args for call in absence.call_args_list] == [
        (settings.AWS_STORAGE_BUCKET_NAME, photo.object_key),
        (settings.AWS_STORAGE_BUCKET_NAME, storage.staging_key(photo.object_key)),
    ]
    download.assert_not_called()
    assert manifest == [{
        "bucket_kind": "private", **ownership, "key": photo.object_key,
        "version_id": None, "size": 0, "sha256": "", "metadata": {},
        "content_type": "", "headers": {},
    }]
    assert list(tmp_path.rglob("*")) == []
    plan.bind_component(MAIN_COMPONENT, tmp_path, manifest)
    plan.verify_component(MAIN_COMPONENT, manifest)
    plan.assert_complete()


def test_reservation_cleanup_preserves_exact_expired_evidence_tombstone(
    upload, tmp_path, monkeypatch, settings,
):
    photo, reservation = upload
    delete = Mock(return_value=SimpleNamespace(absence_confirmed=True))
    monkeypatch.setattr(storage, "_client", lambda: object())
    monkeypatch.setattr("apps.object_storage.delete_all_versions", delete)
    now = reservation.expires_at + timedelta(seconds=1)

    assert cleanup(reservation.pk, now=now) is True

    assert [(call.kwargs["bucket"], call.kwargs["key"])
            for call in delete.call_args_list] == sorted({
        (reservation.bucket, reservation.staging_key),
        (reservation.final_bucket, reservation.object_key),
        (reservation.final_bucket, reservation.final_key),
    })
    reservation.refresh_from_db()
    assert (reservation.released, reservation.converted) == (True, False)
    assert EvidenceObjectRetentionState.objects.get(evidence=photo).object_expired_at == now
    assert AuditLog.objects.filter(
        makerspace=photo.makerspace, action="storage.upload_reservation_released",
    ).count() == 1
    assert_expired_capture(photo, 0, tmp_path, monkeypatch, settings)


def test_converted_photo_retention_preserves_exact_expired_evidence_tombstone(
    upload, tmp_path, monkeypatch, settings,
):
    settings.EVIDENCE_OBJECT_EXPIRY_ENABLED = True
    settings.EVIDENCE_OBJECT_RETENTION_DAYS = 30
    photo, reservation = upload
    EvidenceUploadFinalization.objects.create(
        evidence=photo, status="finalized", size_bytes=6,
    )
    charge_storage_once(photo, 6)
    reservation.refresh_from_db()
    assert (reservation.converted, reservation.released) == (True, False)
    assert EvidenceUploadFinalization.objects.get(evidence=photo).quota_charged is True
    deleted = Mock(return_value="deleted")
    monkeypatch.setattr(storage, "object_size", lambda _key: 6)
    monkeypatch.setattr(storage, "delete_object_strict", deleted)

    summary = sweep_evidence_retention(now=timezone.now() + timedelta(days=31))

    assert (summary["photos_expired"], summary["photos_failed"],
            summary["bytes_removed"]) == (1, 0, 6)
    assert [call.args for call in deleted.call_args_list] == [
        (photo.object_key,), (storage.staging_key(photo.object_key),),
    ]
    reservation.refresh_from_db()
    assert (reservation.released, reservation.converted) == (True, True)
    photo.makerspace.refresh_from_db()
    assert photo.makerspace.storage_bytes_used == 0
    assert AuditLog.objects.filter(
        makerspace=photo.makerspace, action="evidence.object_expired",
        target_id=str(photo.pk),
    ).count() == 1
    assert_expired_capture(photo, 6, tmp_path, monkeypatch, settings)
