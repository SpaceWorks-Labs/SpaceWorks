"""Decision 543: a leaked transaction is attributed and removed before flush."""
from types import SimpleNamespace
from time import monotonic, sleep
from unittest.mock import MagicMock, call

import pytest
from django.db import connection, connections

import conftest as harness


@pytest.mark.django_db(transaction=True)
def test_guard_terminates_a_deliberately_leaked_idle_transaction(request):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL backend activity")
    leaked = connection.copy()
    try:
        leaked.set_autocommit(False)
        with leaked.cursor() as cursor:
            cursor.execute("SELECT pg_backend_pid()")
            pid = cursor.fetchone()[0]
        with connection.cursor() as cursor:
            cursor.execute("SELECT state FROM pg_stat_activity WHERE pid = %s", [pid])
            assert cursor.fetchone() == ("idle in transaction",)
        guard = harness._transaction_connection_hygiene.__wrapped__(request)
        next(guard)
        with pytest.raises(pytest.fail.Exception) as failure:
            next(guard)
        assert str(failure.value) == (
            f"Connection hygiene failure in {request.node.nodeid}: leaked idle-in-transaction "
            f"backends in {connection.settings_dict['NAME']} (pid, terminated): [({pid}, True)]. "
            "Close connections in each worker's finally block and join threads with a timeout."
        )
        deadline = monotonic() + 5
        while True:
            with connection.cursor() as cursor:
                cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE pid = %s", [pid])
                remaining = cursor.fetchone()[0]
            if remaining == 0:
                break
            assert monotonic() < deadline, "Terminated backend did not exit before flush"
            sleep(0.01)
        assert remaining == 0
    finally:
        leaked.close()


@pytest.mark.django_db(transaction=True)
def test_ordinary_transactional_test_keeps_its_connection(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        assert cursor.fetchone() == (1,)
    harness._check_transaction_connection_hygiene(request.node.nodeid)
    with connection.cursor() as cursor:
        cursor.execute("SELECT 2")
        assert cursor.fetchone() == (2,)


@pytest.mark.django_db(transaction=True)
def test_guard_closes_registered_extra_alias_before_scanning(request, allow_projection_databases):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL backend activity")
    alias = "hygiene_extra"
    extra = connection.copy(alias=alias)
    connections.databases[alias] = extra.settings_dict
    connections[alias] = extra
    try:
        extra.set_autocommit(False)
        with extra.cursor() as cursor:
            cursor.execute("SELECT 1")
        harness._check_transaction_connection_hygiene(request.node.nodeid)
        assert extra.connection is None
    finally:
        extra.close()
        del connections[alias]
        del connections.databases[alias]


@pytest.mark.django_db(transaction=True)
def test_guard_leaves_an_idle_autocommit_backend_usable(request):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL backend activity")
    other = connection.copy()
    try:
        with other.cursor() as cursor:
            cursor.execute("SELECT pg_backend_pid()")
            pid = cursor.fetchone()[0]
        harness._check_transaction_connection_hygiene(request.node.nodeid)
        with other.cursor() as cursor:
            cursor.execute("SELECT pg_backend_pid()")
            assert cursor.fetchone() == (pid,)
    finally:
        other.close()


def test_guard_refuses_a_non_test_database_before_closing_or_terminating(monkeypatch):
    cursor = MagicMock()
    cursor.fetchone.return_value = ("spaceworks",)
    database = MagicMock(vendor="postgresql")
    database.cursor.return_value.__enter__.return_value = cursor
    monkeypatch.setattr("django.db.connection", database)
    close_aliases = MagicMock()
    monkeypatch.setattr(connections, "all", close_aliases)
    with pytest.raises(RuntimeError) as failure:
        harness._check_transaction_connection_hygiene("unsafe::test")
    assert type(failure.value) is RuntimeError
    assert str(failure.value) == "Refusing connection cleanup outside a test_ database: spaceworks"
    assert cursor.execute.call_args_list == [call("SELECT current_database()")]
    close_aliases.assert_not_called()


@pytest.mark.parametrize("mode", ["transaction", "reset_sequences", "serialized_rollback",
                                  "transactional_db", "django_db_reset_sequences", "django_db_serialized_rollback"])
def test_guard_acquires_the_database_fixture_before_its_finalizer(monkeypatch, mode):
    events = []
    fixture_only = mode in {"transactional_db", "django_db_reset_sequences", "django_db_serialized_rollback"}
    request = SimpleNamespace(
        node=SimpleNamespace(
            nodeid="transactional::test",
            get_closest_marker=lambda _: None if fixture_only else SimpleNamespace(kwargs={mode: True}),
        ),
        fixturenames=[mode],
        getfixturevalue=events.append,
    )
    monkeypatch.setattr(harness, "_check_transaction_connection_hygiene", events.append)
    fixture = harness._transaction_connection_hygiene.__wrapped__(request)
    next(fixture)
    assert events == ["_django_db_helper"]
    with pytest.raises(StopIteration):
        next(fixture)
    assert events == ["_django_db_helper", "transactional::test"]


@pytest.mark.parametrize("marker", [None, SimpleNamespace(kwargs={"transaction": False})])
def test_nontransactional_test_does_not_acquire_a_database_or_run_cleanup(monkeypatch, marker):
    events = []
    request = SimpleNamespace(
        node=SimpleNamespace(get_closest_marker=lambda _: marker),
        fixturenames=[], getfixturevalue=events.append,
    )
    monkeypatch.setattr(harness, "_check_transaction_connection_hygiene", events.append)
    fixture = harness._transaction_connection_hygiene.__wrapped__(request)
    next(fixture)
    with pytest.raises(StopIteration):
        next(fixture)
    assert events == []


def test_pool_joins_workers_even_when_the_test_body_fails():
    completed = []
    with pytest.raises(ValueError, match="^body failed$"):
        with harness._BoundedThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(completed.append, "closed")
            assert future.result(timeout=5) is None
            raise ValueError("body failed")
    assert completed == ["closed"]
    assert all(not worker.is_alive() for worker in pool._threads)


@pytest.mark.parametrize("exc_type", [None, ValueError])
def test_pool_reports_workers_that_exceed_the_shared_join_deadline(monkeypatch, exc_type):
    pool = harness._BoundedThreadPoolExecutor(max_workers=1)
    worker = MagicMock(name="worker")
    worker.name = "leaked-worker"
    worker.is_alive.return_value = True
    pool._threads.add(worker)
    shutdown = MagicMock()
    monkeypatch.setattr(pool, "shutdown", shutdown)
    monkeypatch.setattr(harness, "monotonic", lambda: 100)
    try:
        with pytest.raises(pytest.fail.Exception) as failure:
            pool.__exit__(exc_type, None, None)
        assert str(failure.value) == (
            "Connection hygiene failure: test workers did not join within 30s: ['leaked-worker']"
        )
        worker.join.assert_called_once_with(timeout=30)
        shutdown.assert_called_once_with(wait=False, cancel_futures=exc_type is not None)
    finally:
        pool._threads.clear()
