"""R2-02/05: final eligibility and recoverable signing after incomplete promotion."""
from threading import Event

import pytest
from botocore.exceptions import EndpointConnectionError
from django.db import close_old_connections, connection, connections, transaction

from conftest import _BoundedThreadPoolExecutor as ThreadPoolExecutor
from apps.audit.models import AuditLog
from apps.devices.models import AdapterArtifact
from apps.makerspaces.models import Makerspace, StorageQuotaReservation as Reservation
from apps.makerspaces.storage_reservations import completion_claim, reserved_bytes
from apps.operations.models import CloudObjectReservation
from tests.devices.test_artifact_reserved_signer_wp_prodfix1 import real_artifact
from tests.machines.test_document_deletion_wp_prodfix2 import used
from tests.modules.switch_matrix_object_helpers import response_pair

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_devices]


def stored(space):
    return AuditLog.objects.filter(makerspace=space, action="devices.adapter_artifact_stored").count()


def test_disable_only_artifacts_while_promoting_refuses_commit_then_restores_once(settings, monkeypatch):
    case, _, _, row, debt, provider, _, _ = real_artifact(settings, monkeypatch, ready=False)
    entered, release = Event(), Event()
    put = provider.put_object.side_effect

    def stalled(**kwargs):
        assert connection.in_atomic_block is False
        entered.set()
        assert release.wait(timeout=12)
        return put(**kwargs)

    provider.put_object.side_effect = stalled

    def complete():
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '3s'")
                cursor.execute("SELECT pg_backend_pid()")
                pid = cursor.fetchone()[0]
            return pid, case["sim"].post(f"artifacts/{row.pk}/complete")
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(complete)
        try:
            assert entered.wait(timeout=5)
            with transaction.atomic():
                space = Makerspace.objects.select_for_update(nowait=True).get(pk=case["space"].pk)
                features = list(space.enabled_features)
                space.enabled_features = [key for key in features if key != "machines.integrations.artifacts"]
                space.save(update_fields=["enabled_features"])
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                main_pid = cursor.fetchone()[0]
            assert future.done() is False
        finally:
            release.set()
        pid, response = future.result(timeout=10)
    assert pid != main_pid
    assert response_pair(response) == (404, "not_found")
    row.refresh_from_db()
    debt.refresh_from_db()
    assert (row.status, debt.cleaning, debt.converted, used(space), reserved_bytes(space), stored(space)) == (
        "pending", False, False, 0, 4, 0)
    assert space.enabled_modules == case["space"].enabled_modules
    space.enabled_features = features
    space.save(update_fields=["enabled_features"])
    response = case["sim"].post(f"artifacts/{row.pk}/complete")
    assert response_pair(response) == (200, None)
    assert (used(space), reserved_bytes(space), stored(space)) == (4, 0, 1)
    assert response_pair(case["sim"].post(f"artifacts/{row.pk}/complete")) == (200, None)
    assert (used(space), stored(space)) == (4, 1)


@pytest.mark.parametrize("failure", ["missing", "provider", "abandoned"])
def test_failed_completion_replay_keeps_original_live_authorizations_and_then_charges_once(failure, settings, monkeypatch):
    case, body, first, row, debt, provider, objects, _ = real_artifact(settings, monkeypatch, ready=False)
    before = Reservation.objects.values().get(pk=debt.pk)
    physical = list(CloudObjectReservation.objects.values())
    read = provider.get_object.side_effect
    if failure == "missing":
        objects.clear()
    elif failure == "provider":
        provider.get_object.side_effect = EndpointConnectionError(endpoint_url="https://timeout.test")
    else:
        # A worker died after its durable claim committed, releasing its fence.
        with transaction.atomic():
            space = Makerspace.objects.select_for_update().get(pk=case["space"].pk)
            claimed, _ = completion_claim(space, row)
        assert claimed.cleaning is True
    if failure != "abandoned":
        response = case["sim"].post(f"artifacts/{row.pk}/complete")
        assert response_pair(response) == ((409, "upload_missing") if failure == "missing" else (503, "storage_unavailable"))
        assert Reservation.objects.values().get(pk=debt.pk) == before
    provider.get_object.side_effect = read
    replay = case["sim"].post("artifacts", body)
    assert response_pair(replay) == (201, None)
    assert (replay.data["artifact_id"], replay.data["duplicate"], replay.data["expires_at"]) == (
        first.data["artifact_id"], True, first.data["expires_at"])
    assert Reservation.objects.values().get(pk=debt.pk) == before
    assert list(CloudObjectReservation.objects.values()) == physical
    assert (Reservation.objects.count(), CloudObjectReservation.objects.count()) == (1, 1)
    assert (used(case["space"]), reserved_bytes(case["space"]), stored(case["space"])) == (0, 4, 0)
    assert AuditLog.objects.filter(makerspace=case["space"], action="devices.adapter_artifact_requested").count() == 1
    objects[debt.staging_key] = b"jpeg"
    assert response_pair(case["sim"].post(f"artifacts/{row.pk}/complete")) == (200, None)
    assert (used(case["space"]), reserved_bytes(case["space"]), stored(case["space"])) == (4, 0, 1)


def test_artifact_object_fence_connection_failure_has_exact_http_error_and_no_charge(settings, monkeypatch):
    from tests.machines.test_object_fence_wp_prodfix5 import fail_fence_connection
    case, _, _, row, debt, provider, _, _ = real_artifact(settings, monkeypatch, ready=False)
    connect = fail_fence_connection(monkeypatch)
    response = case["sim"].post(f"artifacts/{row.pk}/complete")
    assert response_pair(response) == (503, "storage_unavailable")
    assert (used(case["space"]), reserved_bytes(case["space"]), stored(case["space"])) == (0, 4, 0)
    debt.refresh_from_db()
    assert (debt.cleaning, debt.converted, debt.released) == (False, False, False)
    provider.put_object.assert_not_called()
    connect.assert_called_once()


def test_second_artifact_completion_times_out_with_typed_error_then_winner_commits_once(settings, monkeypatch):
    from tests.parity_0120.adapter_api.adapter_case import SimAdapter
    case, _, _, row, debt, provider, _, _ = real_artifact(settings, monkeypatch, ready=False)
    second_client = SimAdapter(case["device"], case["sim"].private)
    entered, release = Event(), Event()
    put = provider.put_object.side_effect

    def stalled(**kwargs):
        assert connection.in_atomic_block is False
        entered.set()
        assert release.wait(timeout=20)
        return put(**kwargs)

    provider.put_object.side_effect = stalled

    def winner():
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '3s'")
                cursor.execute("SELECT pg_backend_pid()")
                pid = cursor.fetchone()[0]
            return pid, case["sim"].post(f"artifacts/{row.pk}/complete")
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(winner)
        try:
            assert entered.wait(timeout=5)
            deletes = provider.delete_object.call_count
            response = second_client.post(f"artifacts/{row.pk}/complete")
            assert response_pair(response) == (503, "storage_unavailable")
            assert first.done() is False
            assert AdapterArtifact.objects.get(pk=row.pk).status == "pending"
            assert (used(case["space"]), reserved_bytes(case["space"]), stored(case["space"])) == (0, 4, 0)
            assert (provider.put_object.call_count, provider.delete_object.call_count) == (1, deletes)
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                main_pid = cursor.fetchone()[0]
        finally:
            release.set()
        pid, response = first.result(timeout=10)
    assert pid != main_pid
    assert response_pair(response) == (200, None)
    assert (used(case["space"]), reserved_bytes(case["space"]), stored(case["space"])) == (4, 0, 1)
    assert response_pair(second_client.post(f"artifacts/{row.pk}/complete")) == (200, None)
    assert (provider.put_object.call_count, used(case["space"]), stored(case["space"])) == (1, 4, 1)


def test_failure_release_does_not_clear_a_replacement_claim(settings, monkeypatch):
    from apps.makerspaces.storage_reservation_cleanup import release_artifact_claim
    case, _, _, row, debt, _, _, _ = real_artifact(settings, monkeypatch, ready=False)
    with transaction.atomic():
        space = Makerspace.objects.select_for_update().get(pk=case["space"].pk)
        old, version = completion_claim(space, row)
    with transaction.atomic():
        space = Makerspace.objects.select_for_update().get(pk=space.pk)
        current, current_version = completion_claim(space, row)
    assert (old.pk == current.pk, version != current_version) == (True, True)
    release_artifact_claim(row, old, version)
    debt.refresh_from_db()
    assert (debt.cleaning, debt.converted, debt.released) == (True, False, False)
    assert (used(space), reserved_bytes(space), stored(space)) == (0, 4, 0)
