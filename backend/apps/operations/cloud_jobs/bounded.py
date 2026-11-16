"""Explicit cooperative bounds for existing domain sweeps; inert outside chunks.

Domain services opt in at their discovery/row loops. Stable primary-key cursors
survive deletion, unlike offsets. A cursor advances only after the caller's row
effect returns. Exceptions leave that row for its domain's existing lease/CAS.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

from .contracts import BudgetExpired, ChunkResult, GuardLost

_scope = ContextVar("cloud_bounded_chunk", default=None)


class _StopChunk(BaseException):
    """Domain catch-and-count handlers must not swallow an execution fence."""
    def __init__(self, cause):
        self.cause = cause


@dataclass
class Progress:
    context: object
    cursors: dict = field(default_factory=dict)
    done: set = field(default_factory=set)
    processed: int = 0
    incomplete: bool = False
    partial: set = field(default_factory=set)

    def check(self):
        try:
            self.context.check()
        except (BudgetExpired, GuardLost) as exc:
            raise _StopChunk(exc) from None
        if self.processed >= self.context.limit:
            self.incomplete = True
            raise _StopChunk(BudgetExpired())

    def result(self):
        complete = not self.incomplete
        return ChunkResult(complete, {} if complete else {
            "cursors": self.cursors, "done": sorted(self.done)}, self.processed)


@contextmanager
def scope(context):
    progress = Progress(context, dict(context.checkpoint.get("cursors", {})),
                        set(context.checkpoint.get("done", [])))
    token = _scope.set(progress)
    try:
        yield progress
    finally:
        _scope.reset(token)


def defer():
    """A domain that bounds its own work reports that rows remain for the next chunk."""
    progress = _scope.get()
    if progress is not None:
        progress.incomplete = True


def check():
    progress = _scope.get()
    if progress is not None:
        progress.check()


def active():
    return _scope.get() is not None


def require_complete(label):
    progress = _scope.get()
    if progress is not None and label in progress.partial:
        raise _StopChunk(BudgetExpired())


def delete(rows, label):
    """Retain Django's bulk-delete behaviour on full, bound selected IDs on free."""
    if not active():
        return rows.delete()
    count = 0
    details = {}
    for row in page(rows, label):
        deleted, labels = rows.model.objects.filter(pk=row.pk).delete()
        count += deleted
        for key, value in labels.items():
            details[key] = details.get(key, 0) + value
    return count, details


def limit(default):
    progress = _scope.get()
    return default if progress is None else min(default, max(1, progress.context.limit - progress.processed))


# A heavy row effect (scan, render, validation, object I/O) takes one row per chunk so
# it can never outlive the tick's total deadline.
HEAVY_ROWS = 1


def rows(default, *, heavy=False):
    """A domain sweep's batch size: unchanged outside a chunk, the chunk's remaining
    limit inside one, and HEAVY_ROWS for heavy row effects."""
    size = limit(default)
    return min(size, HEAVY_ROWS) if heavy and active() else size


def page(rows, label, *, key="pk"):
    """Yield a stable page of model rows, IDs, or values dictionaries.

    Labels must include the parent primary key for nested discovery. Do not turn
    this generator into a list before executing row effects.
    """
    progress = _scope.get()
    if progress is None:
        yield from rows.iterator(chunk_size=100) if hasattr(rows, "iterator") else rows
        return
    if label in progress.done:
        return
    progress.check()
    cursor = progress.cursors.get(label)
    # Existing domain slices remain bounds, but cannot be filtered after slicing.
    if hasattr(rows, "query"):
        rows = rows.all()
        bound = rows.query.high_mark
        rows.query.clear_limits()
        if cursor is not None:
            rows = rows.filter(**{key + "__gt": cursor})
        if rows._iterable_class.__name__ == "ValuesIterable":
            from django.db.models import F
            rows = rows.annotate(_cloud_cursor=F(key))
        size = min(progress.context.limit, bound or progress.context.limit)
        rows = rows.order_by(key)[:size]
    else:
        def identity(row):
            value = row.get(key) if isinstance(row, dict) else getattr(row, key, row)
            return str(value[0] if isinstance(value, tuple) else value)
        rows = sorted(rows, key=identity)
        if cursor is not None:
            rows = [row for row in rows if identity(row) > str(cursor)]
        size = progress.context.limit
        rows = rows[:size]
    count = 0
    for row in rows:
        progress.check()
        yield row
        value = row.get("_cloud_cursor", row.get(key)) if isinstance(row, dict) else getattr(row, key, row)
        if isinstance(value, tuple):
            value = value[0]
        # Keep the parent selected until all its child pages are exhausted. The
        # caller's row effect has returned, so committed child progress is safe.
        suffix = ":" + str(value)
        if any(name != label and name.endswith(suffix) for name in progress.partial):
            progress.incomplete = True
            raise _StopChunk(BudgetExpired())
        cursor_value = str(value) if not isinstance(value, (str, int)) else value
        from django.db import transaction
        transaction.on_commit(lambda name=label, current=cursor_value: progress.cursors.__setitem__(name, current))
        # Nested row labels are complete once their parent effect returned.
        progress.done = {name for name in progress.done if not name.endswith(suffix)}
        progress.processed += 1
        count += 1
    if count < size:
        from django.db import transaction
        def completed():
            progress.done.add(label)
            progress.cursors.pop(label, None)
        transaction.on_commit(completed)
    else:
        progress.incomplete = True
        progress.partial.add(label)


def items(values):
    """Fence each already bounded value; discovery must be bounded separately."""
    for value in values:
        check()
        yield value
        progress = _scope.get()
        if progress is not None:
            progress.processed += 1
            if progress.processed >= progress.context.limit:
                progress.incomplete = True


def invoke(context, callback):
    with scope(context) as progress:
        try:
            context.check()
            from apps.storage_capabilities.budget import storage_budget
            with storage_budget(deadline=context.deadline, check_active=context.check):
                result = callback()
            context.check()
            if isinstance(result, ChunkResult):
                return result
            if isinstance(result, dict) and result.get("failed"):
                raise RuntimeError("Domain sweep has unresolved failures")
        except BudgetExpired:
            progress.incomplete = True
        except _StopChunk as stop:
            if isinstance(stop.cause, GuardLost):
                raise stop.cause
            progress.incomplete = True
        return progress.result()
