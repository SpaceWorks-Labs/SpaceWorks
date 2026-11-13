"""Durable generation fence for unversioned managed capture.

I registers every HTTP/task/job writer with these boundaries. No row transaction
spans external I/O. Crashes leave active/uncertain rows and the pause intact.
"""

from contextlib import contextmanager
from datetime import timedelta
import uuid
import hashlib

from django.db import transaction
from django.utils import timezone

from apps.audit.services import record

from .admission import ManagedAdmissionError
from .models import ManagedCaptureState, ManagedWriterBoundary


CATEGORIES = frozenset({"web", "worker", "cron", "job", "tick", "presign"})


def writer_key(boundary_id):
    return (734322, int.from_bytes(hashlib.sha256(str(boundary_id).encode("ascii")).digest()[:4], "big") & 0x7fffffff)


class WriterFenceError(ManagedAdmissionError):
    code = "managed_writer_fenced"


def _state():
    state = ManagedCaptureState.objects.select_for_update().filter(pk=1).first()
    if state is None:
        raise WriterFenceError("Managed writer registration is unavailable.")
    return state


class WriterBoundary:
    def __init__(self, row, pin=None):
        self.row = row
        self.pin = pin

    def assert_valid(self):
        if self.pin is not None:
            self.pin.assert_valid()
        state = ManagedCaptureState.objects.filter(pk=1).first()
        from .capture import admitted_capture
        if state is not None and admitted_capture((state.generation, state.paused_by)):
            return
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
    from config.cloud_database.locks import session_locks
    boundary_id = uuid.uuid4()
    with session_locks([writer_key(boundary_id)]) as pin:
        with transaction.atomic():
            state = _state()
            if state.paused_by is not None:
                raise WriterFenceError("Managed capture has closed new writers and presigns.")
            row = ManagedWriterBoundary.objects.create(id=boundary_id, generation=state.generation, category=category)
        boundary = WriterBoundary(row, pin)
        try:
            yield boundary
            pin.assert_valid()
        except BaseException as exc:
            # A failed/lost session leaves the active row even if this update
            # cannot run. Recovery proves lock absence and transfer drain.
            if not pin.poisoned:
                pin.assert_valid()
                if isinstance(exc, WriterFenceError):
                    # A synchronous boundary stopped at its fence with its
                    # original physical session still held. No provider timeout
                    # or lost-session exception is interpreted this way.
                    ManagedWriterBoundary.objects.filter(pk=row.pk).update(finished_at=timezone.now())
                else:
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
        from django.db.models import Max
        from .models_staging import ManagedPresignLease
        latest = ManagedPresignLease.objects.aggregate(latest=Max("expires_at"))["latest"]
        if latest is not None:
            state.drain_until = max(state.drain_until, latest)
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
    from .capture import owner_boundary
    active = ManagedWriterBoundary.objects.filter(finished_at=None)
    exempt = owner_boundary(owner)
    if exempt:
        active = active.exclude(pk=exempt)
    if active.exists():
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
