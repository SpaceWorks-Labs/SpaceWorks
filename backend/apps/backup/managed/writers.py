"""Durable generation fence for unversioned managed capture.

I registers every HTTP/task/job writer with these boundaries. No row transaction
spans external I/O. Crashes leave active/uncertain rows and the pause intact.
"""

from contextlib import contextmanager
from datetime import timedelta
import uuid

from django.db import transaction
from django.utils import timezone

from apps.audit.services import record

from .admission import ManagedAdmissionError
from .models import ManagedCaptureState, ManagedWriterBoundary


CATEGORIES = frozenset({"web", "worker", "cron", "job", "tick", "presign"})


class WriterFenceError(ManagedAdmissionError):
    code = "managed_writer_fenced"


def _state():
    state = ManagedCaptureState.objects.select_for_update().filter(pk=1).first()
    if state is None:
        raise WriterFenceError("Managed writer registration is unavailable.")
    return state


class WriterBoundary:
    def __init__(self, row):
        self.row = row

    def assert_valid(self):
        state = ManagedCaptureState.objects.filter(pk=1).first()
        # A pre-pause writer must stop before its next effect. A single effect
        # already in flight remains active until the boundary has exited.
        if state is None or state.paused_by is not None or state.generation != self.row.generation:
            raise WriterFenceError("Managed capture paused this writer generation.")
        if not ManagedWriterBoundary.objects.filter(pk=self.row.pk, finished_at=None, uncertain=False).exists():
            raise WriterFenceError("Managed writer boundary is no longer active.")


@contextmanager
def writer_boundary(category):
    if category not in CATEGORIES:
        raise WriterFenceError("Unknown managed writer category.")
    with transaction.atomic():
        state = _state()
        if state.paused_by is not None:
            raise WriterFenceError("Managed capture has closed new writers and presigns.")
        row = ManagedWriterBoundary.objects.create(generation=state.generation, category=category)
    boundary = WriterBoundary(row)
    try:
        yield boundary
    except BaseException:
        # An exception does not prove an in-flight remote write stopped. Recovery
        # must reconcile it; age/lease expiry must never count as writer drain.
        ManagedWriterBoundary.objects.filter(pk=row.pk).update(uncertain=True)
        raise
    else:
        ManagedWriterBoundary.objects.filter(pk=row.pk, uncertain=False).update(finished_at=timezone.now())


def pause_capture(owner, guard, *, max_presign_ttl, transfer_bound):
    owner = uuid.UUID(str(owner))
    if not 0 < max_presign_ttl <= 7 * 86400 or not 0 < transfer_bound <= 86400:
        raise WriterFenceError("Capture drain bounds are invalid.")
    guard.assert_valid()
    with transaction.atomic():
        state = _state()
        if state.paused_by is not None:
            if state.paused_by == owner:
                return state  # Retry never shortens the original drain deadline.
            raise WriterFenceError("Another capture owns the durable pause.")
        state.generation += 1
        state.paused_by = owner
        state.paused_at = timezone.now()
        state.drain_until = state.paused_at + timedelta(seconds=max_presign_ttl + transfer_bound)
        state.save(update_fields=["generation", "paused_by", "paused_at", "drain_until"])
        record(None, "deployment.capture_paused", meta={"generation": state.generation})
    return state


def assert_capture_drained(owner, guard):
    guard.assert_valid()
    state = ManagedCaptureState.objects.get(pk=1)
    if state.paused_by != uuid.UUID(str(owner)) or state.drain_until is None:
        raise WriterFenceError("Capture does not own the durable writer pause.")
    if timezone.now() < state.drain_until:
        raise WriterFenceError("Issued presigns and in-flight transfer bounds have not drained.")
    if ManagedWriterBoundary.objects.filter(finished_at=None).exists():
        raise WriterFenceError("Active or uncertain writers prevent capture.")
    return state.generation


def finish_capture(owner, guard):
    """Successful capture only; never invoke this blindly from a finally block."""
    assert_capture_drained(owner, guard)
    with transaction.atomic():
        state = _state()
        if state.paused_by != uuid.UUID(str(owner)):
            raise WriterFenceError("Capture pause ownership changed.")
        guard.assert_valid()
        state.paused_by = state.paused_at = state.drain_until = None
        state.save(update_fields=["paused_by", "paused_at", "drain_until"])
        record(None, "deployment.capture_resumed", meta={"generation": state.generation})
