"""Deletion debt owns exact bucket/key pairs even after the source tenant is gone."""
from django.db import connection, connections
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from apps.evidence import storage
from apps.makerspaces.models import Makerspace, StorageQuotaReservation
from apps.makerspaces.storage_reservations import reserve, record_final_key
from apps.makerspaces.storage_reservation_cleanup import cleanup
from apps.tenant_migration.object_storage import _occupied
from tests.return_helpers import make_space

pytestmark = [pytest.mark.django_db, pytest.mark.area_inventory, pytest.mark.area_tenant_migration]


def reservation(space, *, final_bucket="public-images"):
    key = f"items/{space.pk}/p5-normalized.png"
    return reserve(space.pk, key, 10, bucket="private-stage", final_bucket=final_bucket,
                   staging_key="staging/public-images/" + key, ttl=1)


def deletion(monkeypatch):
    monkeypatch.setattr(storage, "_client", lambda: object())
    delete = Mock(return_value=SimpleNamespace(absence_confirmed=True))
    monkeypatch.setattr("apps.object_storage.delete_all_versions", delete)
    return delete


def test_pending_public_upload_cleans_final_and_stage_in_their_own_buckets(monkeypatch):
    space = make_space("p5-public-buckets")
    row = reservation(space)
    final_key = row.object_key + ".webp"
    assert record_final_key(row.object_key, final_key) == final_key
    assert record_final_key(row.object_key, row.object_key + ".retry") == final_key
    delete = deletion(monkeypatch)
    assert cleanup(row.pk, now=row.expires_at + timedelta(seconds=1)) is True
    assert {(call.kwargs["bucket"], call.kwargs["key"]) for call in delete.call_args_list} == {
        ("private-stage", row.staging_key), ("public-images", row.object_key), ("public-images", final_key)}
    assert StorageQuotaReservation.objects.get(pk=row.pk).released is True


def test_storage_endpoint_change_never_credits_or_deletes_from_the_replacement(settings, monkeypatch):
    row = reservation(make_space("p5-changed-storage"))
    delete = deletion(monkeypatch)
    settings.AWS_S3_ENDPOINT_URL = "https://replacement-storage.example.test"
    with pytest.raises(storage.StorageUnavailable):
        cleanup(row.pk, now=row.expires_at + timedelta(seconds=1))
    delete.assert_not_called()
    assert StorageQuotaReservation.objects.get(pk=row.pk).released is False


def test_purging_the_tenant_cannot_discard_its_pending_object_debt(monkeypatch):
    from django.utils import timezone
    from apps.makerspaces.lifecycle_purge import purge
    from tests.r2_superadmin_local.helpers import superadmin
    space = make_space("p5-orphaned-storage")
    source_id = space.pk
    row = reservation(space)
    Makerspace.objects.filter(pk=source_id).update(archived_at=timezone.now())
    space.refresh_from_db()
    purge(space, superadmin("p5-orphaned-storage-root"))
    assert Makerspace.objects.filter(pk=source_id).count() == 0
    retained = StorageQuotaReservation.objects.get(pk=row.pk)
    assert retained.makerspace_id == source_id
    assert retained.released is False
    delete = deletion(monkeypatch)
    assert cleanup(row.pk, now=row.expires_at + timedelta(seconds=1)) is True
    assert delete.call_count == 2
    assert StorageQuotaReservation.objects.get(pk=row.pk).released is True


@pytest.mark.parametrize("field", ["object_key", "final_key", "staging_key"])
def test_import_cannot_reuse_a_key_owned_by_a_reconciling_reservation(field):
    row = reservation(make_space("p5-import-reserved"))
    key = row.object_key + ".webp"
    record_final_key(row.object_key, key)
    row.refresh_from_db()
    assert _occupied("public_image", getattr(row, field)) is True


@pytest.mark.django_db(transaction=True)
def test_cleanup_retries_a_busy_space_without_holding_a_domain_lock(monkeypatch):
    from conftest import _BoundedThreadPoolExecutor as ThreadPoolExecutor
    from threading import Event
    from django.db import close_old_connections, connection, OperationalError, transaction
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    space = make_space("p5-cleanup-lock")
    row = reservation(space)
    acquired, release = Event(), Event()
    def holder():
        close_old_connections()
        try:
            if connection.vendor == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '5s'")
            with transaction.atomic():
                Makerspace.objects.select_for_update().get(pk=space.pk)
                acquired.set()
                assert release.wait(10)
        finally:
            connections.close_all()
    delete = deletion(monkeypatch)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(holder)
        assert acquired.wait(10)
        try:
            with pytest.raises(OperationalError):
                cleanup(row.pk, now=row.expires_at + timedelta(seconds=1))
            delete.assert_not_called()
            assert StorageQuotaReservation.objects.get(pk=row.pk).released is False
        finally:
            release.set()
        future.result(timeout=15)
    assert cleanup(row.pk, now=row.expires_at + timedelta(seconds=1)) is True
