"""Optional tick budget/fencing context; inert in every full-profile process."""

from contextlib import contextmanager
from contextvars import ContextVar
import math
import time

from django.conf import settings

from .contracts import CapabilityError

_budget = ContextVar("storage_call_budget", default=None)


@contextmanager
def storage_budget(*, deadline, check_active):
    """J supplies its monotonic deadline and live attempt/guard check.

    This context creates no worker/thread and never resumes a lost attempt.
    It does not provide an execution lock: the caller retains its domain guard.
    """
    if getattr(settings, "SPACEWORKS_DEPLOYMENT_PROFILE", "full") != "free":
        yield
        return
    if not callable(check_active) or not isinstance(deadline, (float, int)) or not math.isfinite(deadline):
        raise CapabilityError("storage_budget_invalid")
    token = _budget.set((float(deadline), check_active))
    try:
        checkpoint()
        yield
    finally:
        _budget.reset(token)


def checkpoint():
    if getattr(settings, "SPACEWORKS_DEPLOYMENT_MODE", "host") == "managed":
        from apps.operations.cloud_runtime import check
        from apps.backup.cloud_continuity import check_operation
        check_operation()
        check()
    value = _budget.get()
    if value is None:
        return
    deadline, check_active = value
    if time.monotonic() >= deadline - 1:
        raise CapabilityError("storage_budget_exhausted")
    if check_active() is False:
        raise CapabilityError("storage_attempt_fenced")


def client_options():
    if getattr(settings, "SPACEWORKS_DEPLOYMENT_PROFILE", "full") != "free":
        return {}
    checkpoint()
    remaining = 3.0
    if _budget.get() is not None:
        remaining = min(remaining, (_budget.get()[0] - time.monotonic() - 1) / 2)
    if remaining <= 0:
        raise CapabilityError("storage_budget_exhausted")
    return {"connect_timeout": min(2, remaining), "read_timeout": remaining,
            "retries": {"total_max_attempts": 1}}


def raise_if_fenced(exc):
    """StorageUnavailable can wrap a typed fence; never continue that attempt."""
    current = exc
    while current is not None:
        if isinstance(current, CapabilityError) and current.code == "storage_attempt_fenced":
            raise current
        current = current.__cause__
