"""Managed full-profile execution telemetry, without changing host row semantics."""
from contextvars import ContextVar

from django.conf import settings

from . import journal
from .contracts import admit
from .outcomes import require_success

_active = ContextVar("cloud_full_attempt", default=None)


def begin(task, guard):
    if guard is None:
        return None
    journal.model("CloudTaskState").objects.get_or_create(key=task.key)
    # Due selection belongs to the scheduler's interval/calendar declaration.
    # Completion time must not postpone the next fixed calendar slot.
    row, code = journal.claim(task, guard, due_required=False)
    if row is None:
        raise RuntimeError("Managed task requires reconciliation" if code != "not_due" else "Task not due")
    _active.set(task.key)
    return row


def end(row, task, guard, *, failed=False):
    if row is None:
        return
    try:
        journal.finish(row, task, status="uncertain" if failed else "completed",
                       code="full_task_failed_reconciliation_required" if failed else "",
                       guard=None if failed else guard)
    finally:
        _active.set(None)


class _AdmissionGuard:
    check = staticmethod(admit)


def invoke(task_name, callback):
    if (getattr(settings, "SPACEWORKS_DEPLOYMENT_MODE", "host") != "managed"
            or getattr(settings, "SPACEWORKS_DEPLOYMENT_PROFILE", "full") != "full"):
        return callback()
    from .catalog import periodic_catalog
    task = next((item for item in periodic_catalog() if item.path == task_name), None)
    if task is None or _active.get() == task.key:
        return callback()
    guard = _AdmissionGuard()
    row = begin(task, guard)
    try:
        guard.check()
        result = require_success(callback())
        guard.check()
    except BaseException:
        end(row, task, guard, failed=True)
        raise
    end(row, task, guard)
    return result
