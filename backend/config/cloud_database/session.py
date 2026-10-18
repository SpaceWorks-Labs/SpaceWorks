"""Retain Django's physical session across short ORM transactions and remote I/O.

The execute wrapper checks the captured backend before ORM effects. Explicit
``assert_valid`` calls also fence external effects. A reconnect is never recovery
for an operation whose session lock has disappeared.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

from django.db import OperationalError, connections

from .connection import django_database_spec


class SessionLost(OperationalError):
    code = "database_session_lost"


_pins = ContextVar("spaceworks_database_pins", default={})


@dataclass
class RetainedSession:
    wrapper: object
    physical: object
    pid: int
    locks: dict = field(default_factory=dict)
    poisoned: bool = False

    def discard(self):
        self.poisoned = True
        self.physical.close()
        # A replaced connection must be discarded too, never returned to a pool.
        self.wrapper.close()

    def assert_valid(self):
        if self.poisoned or self.wrapper.connection is not self.physical or self.physical.closed:
            raise SessionLost("The retained PostgreSQL session was lost; restart the operation.")
        try:
            with self.physical.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                if cursor.fetchone()[0] != self.pid:
                    raise SessionLost("The PostgreSQL backend changed during a retained operation.")
                for key in self.locks:
                    classid, objid, subid = lock_identity(key)
                    cursor.execute(
                        "SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_locks WHERE "
                        "locktype = 'advisory' AND pid = pg_backend_pid() AND granted AND mode='ExclusiveLock' "
                        "AND classid = %s::oid AND objid = %s::oid AND objsubid = %s "
                        "AND database = (SELECT oid FROM pg_database WHERE datname = current_database()))",
                        [classid, objid, subid],
                    )
                    if not cursor.fetchone()[0]:
                        raise SessionLost("The retained PostgreSQL advisory lock was lost.")
        except Exception:
            self.poisoned = True
            raise SessionLost("The retained PostgreSQL session or advisory lock was lost.") from None

    def execute(self, execute, sql, params, many, context):
        self.assert_valid()
        return execute(sql, params, many, context)


def lock_identity(key):
    if len(key) == 2:
        return key[0] & 0xFFFFFFFF, key[1] & 0xFFFFFFFF, 2
    unsigned = key[0] & 0xFFFFFFFFFFFFFFFF
    return unsigned >> 32, unsigned & 0xFFFFFFFF, 1


def current_session(using="default"):
    return _pins.get().get(using)


@contextmanager
def retained_session(using="default"):
    """Nested callers share one pin, including nested session/xact audit locks."""
    existing = current_session(using)
    if existing is not None:
        existing.assert_valid()
        yield existing
        existing.assert_valid()
        return
    django_database_spec(using)  # Transaction endpoints refuse before lock SQL.
    wrapper = connections[using]
    wrapper.ensure_connection()
    physical = wrapper.connection
    with physical.cursor() as cursor:
        cursor.execute("SELECT pg_backend_pid()")
        pid = cursor.fetchone()[0]
    pin = RetainedSession(wrapper, physical, pid)
    original_connect = wrapper.connect

    def refuse_reconnect():
        pin.poisoned = True
        raise SessionLost("Reconnect is forbidden while a PostgreSQL session is retained.")

    wrapper.connect = refuse_reconnect
    token = _pins.set({**_pins.get(), using: pin})
    try:
        with wrapper.execute_wrapper(pin.execute):
            yield pin
            pin.assert_valid()
    except BaseException:
        # Closing releases even a partially acquired session lock, including when
        # a transaction is aborted and SQL unlock cannot run.
        pin.discard()
        raise
    finally:
        wrapper.connect = original_connect
        _pins.reset(token)
        if pin.poisoned:
            pin.discard()
