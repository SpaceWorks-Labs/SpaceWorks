"""Total wall-clock cutoff for the Linux single-thread free request worker.

Socket timeouts alone do not bound retries, DNS, CPU or a provider that dribbles
bytes. Interruption is uncertain: it never releases domain/provider claims.
"""
from contextlib import contextmanager
import signal
import threading
import time

from .contracts import GuardLost, JobsUnavailable


class _Interrupted(BaseException):
    pass


def _interrupt(signum, frame):
    raise _Interrupted()


@contextmanager
def total_deadline(deadline):
    if (not hasattr(signal, "setitimer") or threading.current_thread() is not threading.main_thread()
            or signal.getitimer(signal.ITIMER_REAL)[0]):
        raise JobsUnavailable("total_deadline_runtime_unavailable")
    previous = signal.signal(signal.SIGALRM, _interrupt)
    try:
        signal.setitimer(signal.ITIMER_REAL, max(0.001, deadline - time.monotonic()))
        yield
    except _Interrupted:
        raise GuardLost("total_deadline_interrupted_reconciliation_required") from None
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
