"""A stalled document provider must not own the shared tenant accounting lock."""
from threading import Event

import pytest
from botocore.exceptions import EndpointConnectionError
from django.db import close_old_connections, connection, connections, transaction

from conftest import _BoundedThreadPoolExecutor as ThreadPoolExecutor
from apps.machines import services, storage
from apps.machines.models import MachineDocument
from apps.makerspaces.models import Makerspace, StorageQuotaReservation
from tests.machines.test_document_deletion_wp_prodfix2 import setup, used, removals, recompute

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_machines]


@pytest.mark.parametrize("timeout", [False, True])
def test_stalled_provider_allows_same_space_locked_write_and_recompute_then_exact_retry(timeout, monkeypatch, settings):
    w, document, provider, _ = setup(False, monkeypatch, settings)
    entered, release = Event(), Event()
    original_check = provider.before_delete

    def stalled():
        original_check()
        assert connection.in_atomic_block is False
        entered.set()
        assert release.wait(timeout=10)
        if timeout:
            raise EndpointConnectionError(endpoint_url="https://timeout.test")

    provider.before_delete = stalled

    def remove():
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '3s'")
                cursor.execute("SELECT pg_backend_pid()")
                pid = cursor.fetchone()[0]
            try:
                services.remove_document(w.machine, w.actor, document)
                return pid, "removed"
            except storage.StorageUnavailable:
                return pid, "unavailable"
        finally:
            connections.close_all()

    def unrelated_write():
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '2s'")
                cursor.execute("SELECT pg_backend_pid()")
                pid = cursor.fetchone()[0]
            with transaction.atomic():
                space = Makerspace.objects.select_for_update().get(pk=w.space.pk)
                space.name = "Unrelated same-space write completed"
                space.save(update_fields=["name"])
            return pid
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        removing = pool.submit(remove)
        try:
            assert entered.wait(timeout=5)
            receipt = StorageQuotaReservation.objects.get(object_key=document.object_key)
            assert (receipt.cleaning, receipt.released) == (True, False)
            writer_pid = pool.submit(unrelated_write).result(timeout=5)
            assert Makerspace.objects.get(pk=w.space.pk).name == "Unrelated same-space write completed"
            assert not removing.done()
            recompute(w.space, 33)
            assert MachineDocument.objects.filter(pk=document.pk).exists()
            assert (used(w.space), removals(w.space).count()) == (33, 0)
        finally:
            release.set()
        deleting_pid, result = removing.result(timeout=10)
    assert writer_pid != deleting_pid
    assert result == ("unavailable" if timeout else "removed")
    if timeout:
        assert (used(w.space), removals(w.space).count()) == (33, 0)
        assert MachineDocument.objects.filter(pk=document.pk).exists()
        recompute(w.space, 33)
        provider.before_delete = original_check
        services.remove_document(w.machine, w.actor, document)
    assert (used(w.space), used(w.other), removals(w.space).count()) == (23, 41, 1)
    assert not MachineDocument.objects.filter(pk=document.pk).exists()
    receipt.refresh_from_db()
    assert (receipt.cleaning, receipt.released) == (False, True)
    services.remove_document(w.machine, w.actor, document)
    assert (used(w.space), removals(w.space).count()) == (23, 1)
    recompute(w.space, 23)


def test_recovered_receipt_fences_the_old_commit_identity(monkeypatch, settings):
    from apps.makerspaces.storage_reservations import deletion_claim, claimed_receipt

    w, document, _, _ = setup(False, monkeypatch, settings)
    with transaction.atomic():
        space = Makerspace.objects.select_for_update().get(pk=w.space.pk)
        old, old_version = deletion_claim(space, document.object_key, document.size_bytes, charged=True)
    with transaction.atomic():
        space = Makerspace.objects.select_for_update().get(pk=w.space.pk)
        new, new_version = deletion_claim(space, document.object_key, document.size_bytes, charged=True)
    assert old.pk == new.pk
    assert old_version != new_version
    with transaction.atomic():
        assert claimed_receipt(old, old_version) is None
        assert claimed_receipt(new, new_version).pk == new.pk
    assert (used(w.space), removals(w.space).count()) == (33, 0)
