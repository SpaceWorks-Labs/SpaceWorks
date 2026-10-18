"""Bounded, reentrant session advisory locks on the retained ORM connection."""

from contextlib import contextmanager
import time

from .session import SessionLost, retained_session


@contextmanager
def session_locks(keys, *, using="default", timeout=None):
    """timeout=None waits like pg_advisory_lock (the host/full behaviour); a number bounds the wait."""
    keys = sorted(set(tuple(key) for key in keys))
    if any(len(key) not in {1, 2} for key in keys):
        raise ValueError("Advisory keys need one bigint or two integers.")
    deadline = None if timeout is None else time.monotonic() + timeout
    with retained_session(using) as pin:
        acquired = []
        try:
            for key in keys:
                pin.assert_valid()
                if key in pin.locks:
                    pin.locks[key] += 1
                else:
                    placeholders = ", ".join(["%s"] * len(key))
                    if deadline is None:
                        with pin.physical.cursor() as cursor:
                            cursor.execute(f"SELECT pg_advisory_lock({placeholders})", list(key))
                        pin.locks[key] = 1
                    while deadline is not None:
                        pin.assert_valid()
                        with pin.physical.cursor() as cursor:
                            cursor.execute(f"SELECT pg_try_advisory_lock({placeholders})", list(key))
                            locked = cursor.fetchone()[0]
                        if locked:
                            pin.locks[key] = 1
                            break
                        if time.monotonic() >= deadline:
                            raise SessionLost("Another operation holds the PostgreSQL session lock.")
                        time.sleep(min(0.05, max(0, deadline - time.monotonic())))
                acquired.append(key)
            yield pin
            pin.assert_valid()
        finally:
            for key in reversed(acquired):
                try:
                    pin.assert_valid()
                    pin.locks[key] -= 1
                    if pin.locks[key] == 0:
                        # Remove only after the unlock assertion; assert_valid must
                        # keep proving ownership until the final effect is over.
                        placeholders = ", ".join(["%s"] * len(key))
                        with pin.physical.cursor() as cursor:
                            cursor.execute(f"SELECT pg_advisory_unlock({placeholders})", list(key))
                            if cursor.fetchone()[0] is not True:
                                raise SessionLost("PostgreSQL did not release the retained lock.")
                        del pin.locks[key]
                except BaseException:
                    pin.discard()
                    raise
