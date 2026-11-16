"""529: pending and refused objects consume durable capacity on both transports."""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.db import connection, transaction
from rest_framework.exceptions import APIException

from apps.audit.models import AuditLog
from apps.evidence import services_upload, storage
from apps.evidence.finalization import charge_storage_once
from apps.evidence.models import EvidencePhoto, EvidenceUploadFinalization, EvidenceObjectRetentionState
from apps.makerspaces.limits_usage import _storage
from apps.makerspaces.models import Makerspace, StorageQuotaReservation
from apps.makerspaces.storage_reservation_cleanup import cleanup
from apps.makerspaces.storage_reservations import reserved_bytes
from tests.limits_0120.creator_races_cx7 import race_creators
from tests.return_helpers import make_member, make_space

pytestmark = [pytest.mark.django_db, pytest.mark.area_inventory, pytest.mark.area_lending]


def world(settings, monkeypatch, key="storage"):
    settings.MANAGED_PLANS_ENABLED = False
    space = make_space("p5-reservations")
    actor = make_member("p5-uploader", space)
    space.resource_limit_overrides = {key: 10}
    space.save(update_fields=["resource_limit_overrides"])
    provider = Mock(return_value={"url": "https://storage.test/upload", "fields": {}})
    monkeypatch.setattr(services_upload, "presigned_upload", provider)
    return space, actor, provider


def upload(space, actor, size=10, kind="issue"):
    return services_upload.issue_upload(space, actor=actor, evidence_type=kind,
        content_type="image/png", size_bytes=size, consumption_state="unconsumed")[0]


def snapshot(space):
    return [list(model.objects.order_by("pk").values()) for model in (
        EvidencePhoto, EvidenceUploadFinalization, StorageQuotaReservation, AuditLog)] + [
        Makerspace.objects.get(pk=space.pk).storage_bytes_used]


@pytest.mark.parametrize("transport", ["put", "post"])
@pytest.mark.parametrize("key,status,code", [
    ("storage", 400, "limit_reached"), ("storage_evidence_bytes", 409, "storage_evidence_bytes_quota_reached")])
def test_presign_max_then_one_more_is_typed_and_writes_nothing(transport, key, status, code, settings, monkeypatch):
    settings.STORAGE_PRESIGN_METHOD = transport
    space, actor, provider = world(settings, monkeypatch, key)
    photo = upload(space, actor)
    assert reserved_bytes(space) == 10
    provider.assert_called_once_with(photo.object_key, "image/png", max_bytes=10, exact_bytes=10)
    before = snapshot(space)
    with pytest.raises(APIException) as failure:
        upload(space, actor, 1)
    assert (failure.value.status_code, str(failure.value.detail["code"])) == (status, code)
    assert snapshot(space) == before
    assert provider.call_count == 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("key,status,code", [
    ("storage", 400, "limit_reached"), ("storage_evidence_bytes", 409, "storage_evidence_bytes_quota_reached")])
def test_presigns_racing_for_last_capacity_have_one_winner(key, status, code, settings, monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    space, actor, provider = world(settings, monkeypatch, key)
    assert race_creators(lambda _: upload(space, actor)) == [(201, "created"), (status, code)]
    assert (EvidencePhoto.objects.filter(makerspace=space).count(),
            StorageQuotaReservation.objects.filter(makerspace=space).count(), provider.call_count) == (1, 1, 1)


@pytest.mark.parametrize("transport", ["put", "post"])
def test_conversion_uses_actual_bytes_once_and_rollback_retains_debt(transport, settings, monkeypatch):
    settings.STORAGE_PRESIGN_METHOD = transport
    space, actor, _ = world(settings, monkeypatch)
    photo = upload(space, actor)
    EvidenceUploadFinalization.objects.create(evidence=photo, status="finalized", size_bytes=6)
    with transaction.atomic():
        charge_storage_once(photo, 6)
        assert reserved_bytes(space) == 0
        transaction.set_rollback(True)
    assert reserved_bytes(space) == 10
    assert Makerspace.objects.get(pk=space.pk).storage_bytes_used == 0
    charge_storage_once(photo, 6)
    charge_storage_once(photo, 6)
    space.refresh_from_db()
    assert (_storage(space), reserved_bytes(space), space.storage_bytes_used) == (6, 0, 6)


def test_refused_promotion_keeps_reservation_until_confirmed_cleanup(settings, monkeypatch):
    space, actor, _ = world(settings, monkeypatch)
    photo = upload(space, actor)
    EvidenceUploadFinalization.objects.create(evidence=photo, status="finalized", size_bytes=10)
    Makerspace.objects.filter(pk=space.pk).update(resource_limit_overrides={"storage": 9})
    with pytest.raises(APIException) as failure:
        charge_storage_once(photo, 10)
    assert (failure.value.status_code, str(failure.value.detail["code"])) == (400, "limit_reached")
    assert reserved_bytes(space) == 10
    row = StorageQuotaReservation.objects.get(object_key=photo.object_key)
    monkeypatch.setattr(storage, "_client", lambda: object())
    delete = Mock(side_effect=storage.StorageUnavailable())
    monkeypatch.setattr("apps.object_storage.delete_all_versions", delete)
    now = row.expires_at + timedelta(seconds=1)
    with pytest.raises(storage.StorageUnavailable):
        cleanup(row.pk, now=now)
    assert reserved_bytes(space) == 10
    delete.side_effect = None
    delete.return_value = SimpleNamespace(absence_confirmed=True)
    assert cleanup(row.pk, now=now) is True
    assert reserved_bytes(space) == 0
    assert EvidencePhoto.objects.filter(pk=photo.pk).exists()
    assert EvidenceObjectRetentionState.objects.get(evidence=photo).status == "expired"
    assert AuditLog.objects.filter(action="storage.upload_reservation_released").count() == 1
    assert cleanup(row.pk, now=now + timedelta(hours=7)) is True
    assert AuditLog.objects.filter(action="storage.upload_reservation_released").count() == 1


def test_expiry_of_converted_reservation_deletes_only_staging(settings, monkeypatch):
    space, actor, _ = world(settings, monkeypatch)
    photo = upload(space, actor)
    EvidenceUploadFinalization.objects.create(evidence=photo, status="finalized", size_bytes=6)
    charge_storage_once(photo, 6)
    row = StorageQuotaReservation.objects.get(object_key=photo.object_key)
    monkeypatch.setattr(storage, "_client", lambda: object())
    delete = Mock(return_value=SimpleNamespace(absence_confirmed=True))
    monkeypatch.setattr("apps.object_storage.delete_all_versions", delete)
    assert cleanup(row.pk, now=row.expires_at + timedelta(seconds=1)) is True
    assert [call.kwargs["key"] for call in delete.call_args_list] == [storage.staging_key(photo.object_key)]
    assert Makerspace.objects.get(pk=space.pk).storage_bytes_used == 6
    assert not EvidenceObjectRetentionState.objects.filter(evidence=photo).exists()


@pytest.mark.parametrize("key", ["storage", "storage_evidence_bytes"])
def test_omitted_size_signs_only_the_remaining_quota_instead_of_refusing_fitting_evidence(key, settings, monkeypatch):
    space, actor, provider = world(settings, monkeypatch, key)
    photo, _ = services_upload.issue_upload(space, actor=actor, evidence_type="return", content_type="image/png")
    assert StorageQuotaReservation.objects.get(object_key=photo.object_key).size_bytes == 10
    provider.assert_called_once_with(photo.object_key, "image/png", max_bytes=10)
