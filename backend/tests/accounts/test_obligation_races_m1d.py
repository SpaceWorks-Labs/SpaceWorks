"""Real Stage A transactions serialize every new-obligation entry point."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic, sleep

import pytest
from django.db import close_old_connections, connection

from apps.accounts import account_deletion as deletion
from apps.accounts.account_obligations import AccountDeletionPending
from apps.audit.models import AuditLog
from tests.accounts import deletion_factories as f
from tests.accounts.test_reauthentication import PASSWORD
from tests.accounts.test_support_m1d import m1d_config, proven
from tests.accounts.test_writer_fixtures_m1d import WRITERS, writer_case

pytestmark = pytest.mark.django_db(transaction=True)


def connected(function, pids=None, ready=None, sql=None):
    close_old_connections()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET lock_timeout = '8s'")
            cursor.execute("SET statement_timeout = '12s'")
            cursor.execute("SELECT pg_backend_pid()")
            if pids is not None:
                pids.append(cursor.fetchone()[0])
        if ready is not None:
            ready.set()

        def capture(execute, query, params, many, context):
            if sql is not None:
                sql.append(query)
            return execute(query, params, many, context)

        with connection.execute_wrapper(capture):
            return function()
    finally:
        close_old_connections()


def wait_for_lock(pid, future):
    deadline = monotonic() + 5
    while monotonic() < deadline:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_stat_clear_snapshot()")
            cursor.execute("SELECT wait_event_type FROM pg_stat_activity WHERE pid = %s", [pid])
            row = cursor.fetchone()
        if row and row[0] == "Lock":
            return
        if future.done():
            future.result()  # Surface an unexpected writer exception directly.
            break
        sleep(0.01)
    pytest.fail("The competing transaction never waited for Stage A's locks")


@pytest.mark.parametrize("kind", WRITERS)
def test_obligation_waits_for_actual_stage_a_commit_then_refuses(kind, monkeypatch):
    tenant, owner, write, snapshot = writer_case(kind, monkeypatch)
    owner.set_password(PASSWORD)
    owner.save(update_fields=["password"])
    # Every race has an account-owned tenant even before its first new obligation.
    f.request(owner, tenant)
    req = proven(owner)
    before = snapshot()
    locked, release, writer_ready = Event(), Event(), Event()
    pids = []
    original = deletion.collect

    def pause_after_stage_a_locks(*args, **kwargs):
        locked.set()
        assert release.wait(timeout=7)
        return original(*args, **kwargs)

    monkeypatch.setattr(deletion, "collect", pause_after_stage_a_locks)

    def writer():
        try:
            return write()
        except AccountDeletionPending:
            return "refused"

    with ThreadPoolExecutor(max_workers=2) as pool:
        departure = pool.submit(connected, lambda: deletion.request_deletion(req))
        try:
            assert locked.wait(timeout=5)
            competing = pool.submit(connected, writer, pids, writer_ready)
            assert writer_ready.wait(timeout=5)
            wait_for_lock(pids[0], competing)
        finally:
            release.set()
        assert departure.result(timeout=15)["deleted_at"]
        assert competing.result(timeout=15) == ("skipped" if kind == "renewal" else "refused")
    assert snapshot() == before
    owner.refresh_from_db()
    assert owner.deletion_requested_at and not owner.is_active
    assert AuditLog.objects.filter(action="account.deletion_requested", actor=owner).count() == 1
