"""Bounded chunk contract shared with domain owners and the cloud integrator.

Callbacks must checkpoint domain leases and call ``context.check()`` before every
effect, including after remote I/O. A running attempt is NEVER reclaimed by age.
Installation is query-free, explicit, and occurs in AppConfig.ready().
"""
from dataclasses import dataclass, field
import json
import time
from typing import Callable

from django.core.exceptions import ImproperlyConfigured


class JobsUnavailable(Exception):
    code = "jobs_unavailable"


class GuardLost(JobsUnavailable):
    code = "guard_lost_operator_reconciliation_required"


class BudgetExpired(JobsUnavailable):
    code = "budget_exhausted"


@dataclass(frozen=True)
class ChunkResult:
    complete: bool
    checkpoint: dict = field(default_factory=dict)
    processed: int = 0

    def __post_init__(self):
        if type(self.complete) is not bool or type(self.processed) is not int or self.processed < 0:
            raise ValueError("Invalid chunk outcome")
        if not isinstance(self.checkpoint, dict):
            raise ValueError("Checkpoint must be an object")
        # Checkpoints contain domain cursors/IDs only; never bytes, PII or secrets.
        if len(json.dumps(self.checkpoint, allow_nan=False).encode()) > 8192:
            raise ValueError("Checkpoint exceeds 8192 bytes")


@dataclass(frozen=True)
class ChunkContext:
    deadline: float
    fence: Callable[[], None]
    checkpoint: dict
    attempt_id: object
    generation: int
    limit: int = 25

    def remaining(self):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise BudgetExpired()
        return remaining

    def check(self):
        self.remaining()
        self.fence()
        self.remaining()

    def timeout(self, maximum=5.0):
        """Transport adapters must apply this to *total*, not only socket, time."""
        self.check()
        return min(maximum, self.remaining())


_chunks = {}
_admission = None


def install_admission(check):
    """I installs M's uncached runtime/recovery/generation admission here."""
    global _admission
    if not callable(check) or (_admission is not None and _admission is not check):
        raise ImproperlyConfigured("Cloud job admission already installed or invalid")
    _admission = check


def admit():
    if _admission is None:
        raise JobsUnavailable("admission_not_installed")
    try:
        _admission()
    except Exception:
        raise JobsUnavailable("admission_refused") from None


def install_chunk(key, callback):
    from .catalog import all_declarations
    if key not in {task.key for task in all_declarations()} or not callable(callback):
        raise ImproperlyConfigured("Unknown cloud chunk")
    if key in _chunks and _chunks[key] is not callback:
        raise ImproperlyConfigured("Duplicate cloud chunk")
    _chunks[key] = callback


def chunk_for(key):
    # No fallback to an unbounded legacy task, even when Celery is eager.
    return _chunks.get(key)
