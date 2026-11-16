"""Separate pytest worlds for production-shaped autocommit command rehearsals."""
from contextlib import contextmanager
from contextvars import ContextVar

import pytest
from django.db import connection

PHASES = ("on", "cycle")
_phase = ContextVar("cx11b_isolated_phase", default=None)


@pytest.fixture(params=PHASES)
def cx11b_isolated_phase(request):
    """Each invocation gets normal pytest DB isolation and a freshly seeded subject.

    The on case commits its success. The cycle case keeps its original subject
    untouched until the switch is restored. No harness transaction wraps a view.
    """
    token = _phase.set(request.param)
    try:
        yield request.param
    finally:
        _phase.reset(token)


def separate_on_case():
    if not connection.get_autocommit():
        return False
    assert _phase.get() in {"on", "cycle"}, "Autocommit probes need separately seeded pytest phases"
    return _phase.get() == "on"


@contextmanager
def rolled_back():
    """Borrow CX2's TestCase savepoint only; never take its autocommit fallback."""
    assert not connection.get_autocommit(), "Use separately seeded on/cycle worlds for autocommit commands"
    from tests.modules.switch_matrix_object_helpers import rolled_back as testcase_savepoint
    with testcase_savepoint():
        yield
