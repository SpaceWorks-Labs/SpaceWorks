"""Overlapping retention and failed terminal audits retain exactly one byte debt."""
from threading import Event

import pytest
from django.db import close_old_connections, connection, connections, transaction

from conftest import _BoundedThreadPoolExecutor as ThreadPoolExecutor
from apps.audit.models import AuditLog
from apps.devices import services_adapter_artifacts as artifacts
from apps.makerspaces.models import Makerspace
from apps.makerspaces.storage_reservations import reserved_bytes
from tests.devices.test_artifact_reserved_signer_wp_prodfix1 import real_artifact
from tests.machines.test_document_deletion_wp_prodfix2 import used, recompute

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_devices]


@pytest.mark.parametrize("ready", [False, True], ids=["pending-reservation", "ready-charge"])
def test_overlapping_two_connection_sweeps_delete_and_commit_once(ready, settings, monkeypatch):
    case, _, _, row, debt, provider, objects, _ = real_artifact(settings, monkeypatch, ready=ready)
    now = row.expires_at
    entered, release = Event(), Event()
    delete = provider.delete_object.side_effect

    def stalled(**kwargs):
        if kwargs["Key"] == row.object_key:
            assert connection.in_atomic_block is False
            entered.set()
            assert release.wait(timeout=10)
        return delete(**kwargs)

    provider.delete_object.side_effect = stalled
    initial_calls = provider.delete_object.call_count

    def sweep():
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '3s'")
                cursor.execute("SELECT pg_backend_pid()")
                pid = cursor.fetchone()[0]
            return pid, artifacts.purge_expired(now=now, space_id=case["space"].pk)
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(sweep)
        try:
            assert entered.wait(timeout=5)
            second_pid, second_count = pool.submit(sweep).result(timeout=5)
            assert second_count == 0
            assert not first.done()
            assert provider.delete_object.call_count == initial_calls + 1
            # Provider I/O owns only an object fence; ordinary tenant writers proceed.
            with transaction.atomic():
                space = Makerspace.objects.select_for_update(nowait=True).get(pk=case["space"].pk)
                space.name = "Independent artifact tenant write"
                space.save(update_fields=["name"])
            recompute(case["space"], 4 if ready else 0)
            assert (used(case["space"]), reserved_bytes(case["space"])) == ((4, 0) if ready else (0, 4))
        finally:
            release.set()
        first_pid, first_count = first.result(timeout=10)
    assert first_pid != second_pid
    assert first_count + second_count == 1
    row.refresh_from_db()
    debt.refresh_from_db()
    assert (row.status, debt.released, debt.cleaning, used(case["space"]), reserved_bytes(case["space"])) == (
        "purged", True, False, 0, 0)
    assert objects == {}
    assert provider.delete_object.call_count == initial_calls + 2
    assert AuditLog.objects.filter(action="devices.adapter_artifact_purged", makerspace=case["space"]).count() == 1
    assert artifacts.purge_expired(now=now, space_id=case["space"].pk) == 0
    assert provider.delete_object.call_count == initial_calls + 2


@pytest.mark.parametrize("ready", [False, True], ids=["pending-reservation", "ready-charge"])
def test_purge_audit_failure_rolls_back_terminal_marker_and_release_then_retry_commits_once(ready, settings, monkeypatch):
    case, _, _, row, debt, _, objects, _ = real_artifact(settings, monkeypatch, ready=ready)
    original = artifacts.audit.record

    def failed_audit(actor, action, **kwargs):
        if action == "devices.adapter_artifact_purged":
            raise RuntimeError("audit unavailable")
        return original(actor, action, **kwargs)

    monkeypatch.setattr(artifacts.audit, "record", failed_audit)
    assert artifacts.purge_expired(now=row.expires_at, space_id=case["space"].pk) == 0
    row.refresh_from_db()
    debt.refresh_from_db()
    assert (row.status, row.purged_at, debt.released, debt.cleaning) == (
        "ready" if ready else "pending", None, False, True)
    assert objects == {}
    assert (used(case["space"]), reserved_bytes(case["space"])) == ((4, 0) if ready else (0, 4))
    assert AuditLog.objects.filter(action="devices.adapter_artifact_purged", makerspace=case["space"]).count() == 0
    recompute(case["space"], 4 if ready else 0)
    monkeypatch.setattr(artifacts.audit, "record", original)
    assert artifacts.purge_expired(now=row.expires_at, space_id=case["space"].pk) == 1
    row.refresh_from_db()
    debt.refresh_from_db()
    assert (row.status, debt.released, debt.cleaning, used(case["space"]), reserved_bytes(case["space"])) == (
        "purged", True, False, 0, 0)
    assert AuditLog.objects.filter(action="devices.adapter_artifact_purged", makerspace=case["space"]).count() == 1
    assert artifacts.purge_expired(now=row.expires_at, space_id=case["space"].pk) == 0
    recompute(case["space"], 0)
