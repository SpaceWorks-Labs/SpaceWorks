"""R2-06: object coordination refuses with retryable errors, preserving debt."""
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.db import close_old_connections, connection, connections

from conftest import _BoundedThreadPoolExecutor as ThreadPoolExecutor
from apps.evidence.storage import StorageUnavailable
from apps.machines.models import MachineDocument
from apps.makerspaces import storage_reservations as reservations
from tests.machines.test_document_deletion_wp_prodfix2 import setup, used, removals
from tests.modules.switch_matrix_object_helpers import client_for, response_pair

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_machines]


def fail_fence_connection(monkeypatch):
    driver = connection.Database
    connect = Mock(side_effect=driver.OperationalError("object fence connection unavailable"))
    monkeypatch.setattr(reservations, "connection", SimpleNamespace(
        Database=SimpleNamespace(connect=connect, Error=driver.Error),
        get_connection_params=connection.get_connection_params))
    return connect


def test_machine_object_fence_connection_failure_has_exact_http_error_and_no_release(settings, monkeypatch):
    w, document, provider, url = setup(False, monkeypatch, settings)
    connect = fail_fence_connection(monkeypatch)
    response = w.client.delete(url)
    assert response_pair(response) == (503, "storage_unavailable")
    assert (used(w.space), used(w.other), removals(w.space).count(), provider.batches) == (33, 41, 0, [])
    assert MachineDocument.objects.filter(pk=document.pk).exists() is True
    connect.assert_called_once()


def test_second_machine_delete_times_out_with_typed_error_while_winner_releases_once(settings, monkeypatch):
    w, document, provider, url = setup(False, monkeypatch, settings)
    first_client = client_for(w.actor, w.space, False)
    entered, release = Event(), Event()
    calls = []
    before = provider.before_delete

    def stalled():
        assert connection.in_atomic_block is False
        before()
        calls.append("delete")
        entered.set()
        assert release.wait(timeout=20)

    provider.before_delete = stalled

    def winner():
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '3s'")
                cursor.execute("SELECT pg_backend_pid()")
                pid = cursor.fetchone()[0]
            return pid, first_client.delete(url)
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(winner)
        try:
            assert entered.wait(timeout=5)
            response = w.client.delete(url)  # The real dedicated connection's 5s deadline.
            assert response_pair(response) == (503, "storage_unavailable")
            assert first.done() is False
            assert MachineDocument.objects.filter(pk=document.pk).exists() is True
            assert (used(w.space), used(w.other), removals(w.space).count(), provider.batches, calls) == (
                33, 41, 0, [], ["delete"])
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                main_pid = cursor.fetchone()[0]
        finally:
            release.set()
        winner_pid, response = first.result(timeout=10)
    assert winner_pid != main_pid
    assert response_pair(response) == (204, None)
    assert (used(w.space), used(w.other), removals(w.space).count(), len(provider.batches)) == (23, 41, 1, 1)
    assert response_pair(w.client.delete(url)) == (404, "not_found")
    assert (used(w.space), removals(w.space).count(), calls) == (23, 1, ["delete"])


@pytest.mark.parametrize("attribute", ["pgcode", "sqlstate"])
def test_both_driver_lock_timeout_shapes_are_translated_and_connection_is_closed(attribute, monkeypatch):
    class LockTimeout(connection.Database.Error):
        pass

    error = LockTimeout("lock timeout")
    # Both supported drivers' exception families are caught, independent of
    # which version is installed in the orchestrator's runtime.
    setattr(LockTimeout, attribute, "55P03")
    dedicated = Mock()
    dedicated.cursor.return_value.__enter__ = Mock(side_effect=error)
    dedicated.cursor.return_value.__exit__ = Mock()
    dedicated.rollback.side_effect = connection.Database.OperationalError("rollback also failed")
    monkeypatch.setattr(reservations, "connection", SimpleNamespace(
        Database=SimpleNamespace(connect=lambda **_: dedicated, Error=connection.Database.Error),
        get_connection_params=lambda: {}))
    with pytest.raises(StorageUnavailable) as caught:
        with reservations.object_operation("machines/1/document.pdf"):
            raise AssertionError("The body must not run")
    assert caught.value.__cause__ is error
    dedicated.rollback.assert_called_once()
    dedicated.close.assert_called_once()


def test_teardown_cannot_mask_an_application_error_or_skip_connection_close(monkeypatch):
    dedicated = Mock()
    dedicated.cursor.return_value.__enter__ = Mock(return_value=Mock())
    dedicated.cursor.return_value.__exit__ = Mock(return_value=False)
    dedicated.rollback.side_effect = connection.Database.OperationalError("rollback failed")
    dedicated.close.side_effect = connection.Database.OperationalError("close failed")
    monkeypatch.setattr(reservations, "connection", SimpleNamespace(
        Database=SimpleNamespace(connect=lambda **_: dedicated, Error=connection.Database.Error),
        get_connection_params=lambda: {}))
    with pytest.raises(ValueError, match="application refusal"):
        with reservations.object_operation("machines/1/document.pdf"):
            raise ValueError("application refusal")
    dedicated.close.assert_called_once()


@pytest.mark.parametrize("failure", ["rollback", "close"])
def test_teardown_failure_without_a_primary_error_is_retryable(failure, monkeypatch):
    dedicated = Mock()
    dedicated.cursor.return_value.__enter__ = Mock(return_value=Mock())
    dedicated.cursor.return_value.__exit__ = Mock(return_value=False)
    error = connection.Database.OperationalError("fence teardown failed")
    getattr(dedicated, failure).side_effect = error
    monkeypatch.setattr(reservations, "connection", SimpleNamespace(
        Database=SimpleNamespace(connect=lambda **_: dedicated, Error=connection.Database.Error),
        get_connection_params=lambda: {}))
    with pytest.raises(StorageUnavailable) as caught:
        with reservations.object_operation("machines/1/document.pdf"):
            pass
    assert caught.value.__cause__ is error
    dedicated.close.assert_called_once()
