"""Retain the managed operation guard across archive/object effect boundaries."""
from contextlib import contextmanager
from contextvars import ContextVar

_operation = ContextVar("managed_operation_guard", default=None)


def current_operation():
    return _operation.get()


def check_operation():
    guard = _operation.get()
    if guard is not None and hasattr(guard, "assert_valid"):
        guard.assert_valid()


@contextmanager
def operation_guard(guard):
    token = _operation.set(guard)
    try:
        check_operation()
        yield
        check_operation()
    finally:
        _operation.reset(token)


def guarded_effect(callback, *args, **kwargs):
    check_operation()
    result = callback(*args, **kwargs)
    check_operation()
    return result
