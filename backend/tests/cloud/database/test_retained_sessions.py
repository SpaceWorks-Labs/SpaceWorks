"""Real PostgreSQL tests; run only in the integrator's isolated harness."""

import psycopg2
import pytest
from django.db import connection, transaction

from apps.audit.batches import LOCK_NAMESPACE, _scope_lock, scope_session_lock
from config.cloud_database import django_database_spec
from config.cloud_database.guards import transaction_guard
from config.cloud_database.locks import session_locks
from config.cloud_database.session import SessionLost, retained_session


pytestmark = pytest.mark.django_db(transaction=True)


def competing_connection():
    result = psycopg2.connect(**django_database_spec().kwargs())
    result.autocommit = True
    return result


def test_nested_audit_session_and_transaction_locks_use_one_backend():
    with scope_session_lock(1934) as guard:
        pid = guard.pid
        with transaction.atomic():
            _scope_lock(1934)  # Would deadlock if the session lock used another alias.
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                assert cursor.fetchone()[0] == pid
        with scope_session_lock(1934) as nested:
            assert nested is guard
        guard.assert_valid()
        other = competing_connection()
        try:
            with other.cursor() as cursor:
                cursor.execute("SELECT pg_try_advisory_lock(%s, %s)", [LOCK_NAMESPACE, 1934])
                assert cursor.fetchone() == (False,)
        finally:
            other.close()
    other = competing_connection()
    try:
        with other.cursor() as cursor:
            cursor.execute("SELECT pg_try_advisory_lock(%s, %s)", [LOCK_NAMESPACE, 1934])
            assert cursor.fetchone() == (True,)
            cursor.execute("SELECT pg_advisory_unlock(%s, %s)", [LOCK_NAMESPACE, 1934])
            assert cursor.fetchone() == (True,)
    finally:
        other.close()


def test_killed_session_cannot_reconnect_and_continue():
    other = competing_connection()
    effects = []
    try:
        with pytest.raises(SessionLost):
            with scope_session_lock(1935) as guard:
                with other.cursor() as cursor:
                    cursor.execute("SELECT pg_terminate_backend(%s)", [guard.pid])
                    assert cursor.fetchone() == (True,)
                guard.assert_valid()
                effects.append("should-never-happen")
    finally:
        other.close()
    assert effects == []


def test_replacement_physical_connection_is_refused_and_discarded():
    replacement = competing_connection()
    with pytest.raises(SessionLost):
        with scope_session_lock(1936):
            connection.connection = replacement
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
    assert replacement.closed


def test_orm_reconnect_is_forbidden_while_pinned():
    with pytest.raises(SessionLost):
        with retained_session():
            connection.close()
            connection.ensure_connection()


def test_direct_and_declared_session_transport_are_accepted(settings):
    for mode in ("direct", "session"):
        settings.DATABASE_CONNECTION_MODE = mode
        with session_locks([(734_328, 12)]) as guard:
            guard.assert_valid()


def test_transaction_mode_is_refused_before_lock_sql(settings):
    settings.DATABASE_CONNECTION_MODE = "transaction"
    from config.cloud_database import DatabaseConfigurationError
    with pytest.raises(DatabaseConfigurationError):
        with scope_session_lock(1937):
            pytest.fail("transaction endpoint entered a protected operation")


def test_tick_guard_is_transaction_scoped_nonblocking_and_fences_loss():
    spec = django_database_spec()
    with transaction_guard(spec, (734_329, 1)) as first:
        assert first is not None
        with transaction_guard(spec, (734_329, 1)) as contender:
            assert contender is None
        first.assert_valid()
    with transaction_guard(spec, (734_329, 1)) as after_release:
        assert after_release is not None


def test_tick_guard_termination_never_reconnects():
    other = competing_connection()
    try:
        with pytest.raises(Exception):
            with transaction_guard(django_database_spec(), (734_329, 2)) as guard:
                assert guard is not None
                with other.cursor() as cursor:
                    cursor.execute("SELECT pg_terminate_backend(%s)", [guard.pid])
                guard.assert_valid()
    finally:
        other.close()
