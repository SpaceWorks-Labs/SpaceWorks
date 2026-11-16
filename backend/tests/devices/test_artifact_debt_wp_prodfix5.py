"""R2-01/03/04: private artifact debt survives purge, upgrades and cleanup limits."""
from datetime import timedelta
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.devices.models import AdapterArtifact
from apps.devices.services_adapter_artifacts import purge_expired
from apps.machines.models import MachineDocument
from apps.makerspaces import limits
from apps.makerspaces.models import Makerspace, StorageQuotaReservation as Reservation
from apps.makerspaces.module_purge import purge_module
from apps.makerspaces.storage_reservation_cleanup import cleanup, sweep
from apps.makerspaces.storage_reservations import reserved_bytes
from tests.devices.test_artifact_reserved_signer_wp_prodfix1 import real_artifact as signer_artifact
from tests.machines.test_document_deletion_wp_prodfix2 import recompute, used
from tests.module_helpers import disable_module

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_devices]


def real_artifact(settings, monkeypatch, **kwargs):
    result = signer_artifact(settings, monkeypatch, **kwargs)
    monkeypatch.setattr("apps.evidence.storage._client", lambda: result[5])
    return result


def kept_document(case):
    row = MachineDocument.objects.create(machine=case["machine"], doc_type="manual",
        object_key=f"machines/{case['space'].pk}/retained.pdf", original_filename="retained.pdf",
        content_type="application/pdf", size_bytes=23)
    limits.add_storage(case["space"], 23)
    return row


@pytest.mark.parametrize("failure", [None, "final", "staging"])
@pytest.mark.parametrize("claimed", [False, True])
def test_devices_module_purge_retains_exact_private_debt_until_both_keys_are_absent(failure, claimed, settings, monkeypatch):
    case, _, _, row, debt, provider, objects, failing = real_artifact(settings, monkeypatch)
    kept = kept_document(case)
    objects[debt.staging_key] = b"late"
    if failure:
        failing.add(row.object_key if failure == "final" else debt.staging_key)
    # Recover a crashed domain claim as well as an ordinary converted receipt.
    Reservation.objects.filter(pk=debt.pk).update(cleaning=claimed)
    delete = provider.delete_object.side_effect

    def outside_locks(**kwargs):
        assert connection.in_atomic_block is False
        return delete(**kwargs)

    provider.delete_object.side_effect = outside_locks
    assert (used(case["space"]), reserved_bytes(case["space"])) == (27, 0)
    disable_module(case["space"], "devices")
    root = get_user_model().objects.create_superuser("artifact-purge-root", "root@example.test", "secret")
    counts = purge_module(case["space"], "devices", root)
    assert counts["adapter_artifacts"] == 1
    assert AdapterArtifact.objects.filter(pk=row.pk).exists() is False
    assert MachineDocument.objects.filter(pk=kept.pk).exists() is True
    debt.refresh_from_db()
    expected = 27 if failure else 23
    assert (used(case["space"]), debt.converted, debt.released) == (expected, True, failure is None)
    recompute(case["space"], expected)
    recompute(case["space"], expected)
    if failure:
        assert objects[row.object_key if failure == "final" else debt.staging_key] == (b"jpeg" if failure == "final" else b"late")
        assert debt.cleaning is True
        assert AuditLog.objects.filter(action="storage.upload_reservation_released", makerspace=case["space"]).count() == 0
        failing.clear()
        assert cleanup(debt.pk) is True
    assert objects == {}
    assert used(case["space"]) == 23
    # A scheduled reconciliation can re-delete late bytes without another release.
    objects[debt.staging_key] = b"late"
    debt.refresh_from_db()
    assert cleanup(debt.pk, now=debt.expires_at) is True
    assert objects == {}
    assert used(case["space"]) == 23
    assert AuditLog.objects.filter(action="storage.upload_reservation_released", makerspace=case["space"]).count() == 1
    recompute(case["space"], 23)


@pytest.mark.parametrize("receipt_kind", ["missing", "unconverted"])
@pytest.mark.parametrize("reconcile_first", [False, True])
def test_legacy_ready_artifact_never_subtracts_an_unrelated_charge(receipt_kind, reconcile_first, settings, monkeypatch):
    case, _, _, row, debt, _, objects, failing = real_artifact(settings, monkeypatch, ready=False)
    kept_document(case)
    AdapterArtifact.objects.filter(pk=row.pk).update(status="ready")
    objects[row.object_key] = objects.pop(debt.staging_key)
    if receipt_kind == "missing":
        debt.delete()
    assert used(case["space"]) == 23
    if reconcile_first:
        recompute(case["space"], 27)
        recompute(case["space"], 27)
        receipt = Reservation.objects.get(object_key=row.object_key)
        assert (receipt.size_bytes, receipt.converted, receipt.released) == (4, True, False)
        assert reserved_bytes(case["space"]) == 0
    failing.add(row.object_key)
    assert purge_expired(now=row.expires_at, space_id=case["space"].pk) == 0
    expected = 27 if reconcile_first else 23
    assert used(case["space"]) == expected
    assert AdapterArtifact.objects.get(pk=row.pk).status == "ready"
    assert AuditLog.objects.filter(action="devices.adapter_artifact_purged", makerspace=case["space"]).count() == 0
    failing.clear()
    assert purge_expired(now=row.expires_at, space_id=case["space"].pk) == 1
    assert used(case["space"]) == 23
    assert objects == {}
    assert AuditLog.objects.filter(action="devices.adapter_artifact_purged", makerspace=case["space"]).count() == 1
    recompute(case["space"], 23)
    recompute(case["space"], 23)
    assert purge_expired(now=row.expires_at, space_id=case["space"].pk) == 0


@pytest.mark.parametrize("cleaning", [False, True])
def test_bounded_cleanup_skips_owned_artifacts_before_slicing_and_recovers_orphan(cleaning, settings, monkeypatch):
    case, _, _, artifact, debt, _, objects, _ = real_artifact(settings, monkeypatch)
    expired = timezone.now() - timedelta(hours=1)
    Reservation.objects.filter(pk=debt.pk).update(expires_at=expired, cleaning=cleaning)
    for number in range(3):
        key = f"adapter-artifacts/{case['space'].pk}/{artifact.binding_id}/owned-{number}"
        AdapterArtifact.objects.create(makerspace=case["space"], binding_id=artifact.binding_id,
            operation_id=uuid4(), kind="thumbnail", content_type="image/jpeg", size_bytes=4,
            object_key=key, status="pending", expires_at=artifact.expires_at, captured_at=timezone.now())
        Reservation.objects.create(makerspace=case["space"], object_key=key, final_key=key,
            staging_key="staging/" + key, bucket=debt.bucket, final_bucket=debt.final_bucket,
            storage_endpoint=debt.storage_endpoint, kind=debt.kind, size_bytes=4, expires_at=expired, cleaning=cleaning)
    before = list(Reservation.objects.order_by("pk").values())
    key = f"machines/{case['space'].pk}/ordinary.pdf"
    ordinary = Reservation.objects.create(makerspace=case["space"], object_key=key, final_key=key,
        staging_key="staging/" + key, bucket=debt.bucket, final_bucket=debt.final_bucket,
        storage_endpoint=debt.storage_endpoint, kind=debt.kind, size_bytes=7, expires_at=expired + timedelta(minutes=1))
    objects[ordinary.staging_key] = b"pending"
    assert sweep(limit=3) == 1
    ordinary.refresh_from_db()
    assert ordinary.released is True
    assert list(Reservation.objects.exclude(pk=ordinary.pk).order_by("pk").values()) == before
    assert objects == {artifact.object_key: b"jpeg"}
    # An orphan with cleaning=True must not be excluded with active owners.
    orphan_key = f"adapter-artifacts/{case['space'].pk}/orphan"
    orphan = Reservation.objects.create(makerspace=case["space"], object_key=orphan_key, final_key=orphan_key,
        staging_key="staging/" + orphan_key, bucket=debt.bucket, final_bucket=debt.final_bucket,
        storage_endpoint=debt.storage_endpoint, kind=debt.kind, size_bytes=4, expires_at=expired, cleaning=True)
    objects[orphan_key], objects[orphan.staging_key] = b"jpeg", b"late"
    assert sweep(limit=3) == 1
    orphan.refresh_from_db()
    assert (orphan.released, orphan.cleaning, used(case["space"])) == (True, False, 4)
    assert objects == {artifact.object_key: b"jpeg"}
    assert list(Reservation.objects.exclude(pk__in=[ordinary.pk, orphan.pk]).order_by("pk").values()) == before
