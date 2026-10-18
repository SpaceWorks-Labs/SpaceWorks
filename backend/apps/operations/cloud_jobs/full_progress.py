"""Managed full-profile execution telemetry, without changing host row semantics."""
from . import journal


def begin(task, guard):
    if guard is None:
        return None
    journal.model("CloudTaskState").objects.get_or_create(key=task.key)
    row, code = journal.claim(task, guard)
    if row is None:
        raise RuntimeError("Managed task requires reconciliation" if code != "not_due" else "Task not due")
    return row


def end(row, task, guard, *, failed=False):
    if row is None:
        return
    journal.finish(row, task, status="uncertain" if failed else "completed",
                   code="full_task_failed_reconciliation_required" if failed else "",
                   guard=None if failed else guard)
