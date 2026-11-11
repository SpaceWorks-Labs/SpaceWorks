"""Nested M-to-P boundaries must not queue behind an exclusive waiter."""
from contextlib import contextmanager

import pytest

from apps.tenant_migration import gate_runtime


def test_same_tenant_reuses_held_boundary_before_shared_lock_acquisition(monkeypatch):
    acquired, checked = [], []
    @contextmanager
    def shared(tenant):
        # An exclusive waiter would prevent this second connection acquiring a
        # shared lock while it waits for our first connection. Model that refusal.
        assert tenant not in acquired, "Nested connection would deadlock behind the exclusive waiter"
        acquired.append(tenant)
        try:
            yield
        finally:
            acquired.remove(tenant)
    monkeypatch.setattr(gate_runtime, "shared_boundary", shared)
    monkeypatch.setattr(gate_runtime, "_assert_gate_state", checked.append)
    with gate_runtime.boundary_tenant_write(42):
        with gate_runtime.boundary_tenant_write(42):
            assert acquired == [42]
        with gate_runtime.boundary_tenant_write(43):
            assert acquired == [42, 43]
    assert acquired == [] and checked == [42, 42, 43]
    assert gate_runtime._boundary_shared_locks.get() == ()


@pytest.mark.django_db(transaction=True)
def test_nested_boundary_with_real_exclusive_waiter():
    import time
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from apps.tenant_migration.gate_locks import _new_lock_connection, SOURCE_GATE_LOCK_NAMESPACE
    from tests.return_helpers import make_space
    # This test is marked transaction=True below: dedicated connections must see
    # the tenant, and their advisory locks must outlive each application query.
    tenant = make_space("recon-nested-waiter")
    waiting, finished = Event(), Event()
    waiter = {}
    def exclusive():
        connection = _new_lock_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL lock_timeout = '3s'")
                cursor.execute("SELECT pg_backend_pid()")
                waiter["pid"] = cursor.fetchone()[0]
                waiting.set()
                cursor.execute("SELECT pg_advisory_xact_lock(%s, %s)", [SOURCE_GATE_LOCK_NAMESPACE, tenant.pk])
            return True
        finally:
            finished.set()
            connection.close()
    with ThreadPoolExecutor(max_workers=1) as pool:
        with gate_runtime.boundary_tenant_write(tenant.pk):
            future = pool.submit(exclusive)
            assert waiting.wait(2)
            from django.db import connection
            deadline = time.monotonic() + 2
            while True:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT EXISTS(SELECT 1 FROM pg_locks WHERE pid = %s AND NOT granted)", [waiter["pid"]])
                    queued = cursor.fetchone()[0]
                if queued:
                    break
                assert time.monotonic() < deadline
                time.sleep(0.01)
            with gate_runtime.boundary_tenant_write(tenant.pk):
                assert not finished.is_set(), "Nested shared acquisition waited for the exclusive timeout"
        assert future.result(timeout=2) is True

