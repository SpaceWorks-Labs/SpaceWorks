"""A capture owner keeps exclusion while ordinary processes remain fenced."""
from contextlib import contextmanager
from contextvars import ContextVar
import time
import uuid

from django.conf import settings
from django.utils import timezone

_capture = ContextVar("managed_capture_owner", default=None)


def admitted_capture(state):
    entry = _capture.get()
    if entry is None or state is None:
        return False
    owner, guard, _boundary = entry
    guard.assert_valid()
    return state[1] == owner


def owner_boundary(owner):
    entry = _capture.get()
    if entry is not None and entry[0] == uuid.UUID(str(owner)):
        entry[1].assert_valid()
        return entry[2]
    return None


def active_capture():
    entry = _capture.get()
    if entry is None:
        return False
    from .models import ManagedCaptureState
    state = ManagedCaptureState.objects.get(pk=1)
    return admitted_capture((state.generation, state.paused_by))


@contextmanager
def capture_pause(owner, *, sleep=time.sleep, resume=True):
    from apps.backup.cloud_continuity import current_operation
    from apps.operations.cloud_runtime import _writer
    from .writers import pause_capture, assert_capture_drained, finish_capture, WriterFenceError
    guard = current_operation()
    if guard is None or not hasattr(guard, "assert_valid"):
        raise WriterFenceError("Managed capture requires retained operation exclusion.")
    boundary = _writer.get()
    if not resume and boundary is not None:
        raise WriterFenceError("A retained maintenance pause requires a standalone operation owner.")
    # Actual presigns are journalled; this compatibility floor also drains URLs
    # issued by an older release before the new journal existed.
    floor = max(int(settings.BACKUP_PRESIGN_DRAIN_SECONDS),
                int(settings.TENANT_MIGRATION_PRESIGN_DRAIN_SECONDS), 1)
    if floor > 604800:
        raise WriterFenceError("The effective legacy presign floor exceeds the supported capture bound.")
    horizon = getattr(settings, "MANAGED_UPLOAD_TRANSFER_BOUND_SECONDS", 0)
    if not horizon:
        raise WriterFenceError("Verify and configure the provider's enforced upload transfer horizon before capture.")
    state = pause_capture(owner, guard, max_presign_ttl=floor, transfer_bound=horizon)
    token = _capture.set((uuid.UUID(str(owner)), guard, boundary.row.pk if boundary else None))
    try:
        while timezone.now() < state.drain_until:
            guard.assert_valid()
            sleep(min(1, (state.drain_until - timezone.now()).total_seconds()))
        assert_capture_drained(owner, guard)
        yield
        # Only a proved successful capture clears its durable pause. Exceptions,
        # process death and lost guards deliberately leave it for recovery.
        if resume:
            finish_capture(owner, guard)
        if boundary:
            from .models import ManagedCaptureState, ManagedWriterBoundary
            generation = ManagedCaptureState.objects.get(pk=1).generation
            ManagedWriterBoundary.objects.filter(pk=boundary.row.pk).update(generation=generation)
            boundary.row.generation = generation
    finally:
        _capture.reset(token)
