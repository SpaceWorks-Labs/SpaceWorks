from datetime import timedelta
from unittest.mock import Mock
import uuid

import pytest
from django.utils import timezone

from apps.backup.managed.models import ManagedCaptureState, ManagedWriterBoundary
from apps.backup.managed.writers import (
    WriterFenceError, assert_capture_drained, finish_capture, pause_capture, writer_boundary,
)


pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def state(monkeypatch):
    monkeypatch.setattr("apps.backup.managed.writers.record", Mock())
    return ManagedCaptureState.objects.create(pk=1)


def test_pause_closes_new_boundaries_and_fences_existing_generation(state):
    guard = Mock(unsafe=True)  # the guard API is assert_valid()
    owner = uuid.uuid4()
    with writer_boundary("web") as boundary:
        boundary.assert_valid()
        pause_capture(owner, guard, max_presign_ttl=300, transfer_bound=60)
        with pytest.raises(WriterFenceError):
            boundary.assert_valid()
        with pytest.raises(WriterFenceError):
            with writer_boundary("tick"):
                pytest.fail("new writer admitted during pause")
        with pytest.raises(WriterFenceError):
            assert_capture_drained(owner, guard)
    assert ManagedWriterBoundary.objects.get(pk=boundary.row.pk).finished_at is not None


def test_crash_keeps_an_uncertain_boundary_and_never_clears_pause(state):
    guard = Mock(unsafe=True)  # the guard API is assert_valid()
    owner = uuid.uuid4()
    with pytest.raises(RuntimeError):
        with writer_boundary("worker"):
            raise RuntimeError("simulated lost worker")
    pause_capture(owner, guard, max_presign_ttl=1, transfer_bound=1)
    ManagedCaptureState.objects.filter(pk=1).update(drain_until=timezone.now() - timedelta(seconds=1))
    with pytest.raises(WriterFenceError, match="uncertain"):
        assert_capture_drained(owner, guard)
    state.refresh_from_db()
    assert state.paused_by == owner
    assert ManagedWriterBoundary.objects.filter(uncertain=True, finished_at=None).count() == 1


def test_presign_and_transfer_deadline_cannot_be_shortened_by_retry(state):
    guard = Mock(unsafe=True)  # the guard API is assert_valid()
    owner = uuid.uuid4()
    first = pause_capture(owner, guard, max_presign_ttl=3600, transfer_bound=60)
    second = pause_capture(owner, guard, max_presign_ttl=1, transfer_bound=1)
    assert first.drain_until == second.drain_until
    with pytest.raises(WriterFenceError):
        assert_capture_drained(owner, guard)


def test_lost_capture_guard_never_clears_a_pause(state):
    guard = Mock(unsafe=True)  # the guard API is assert_valid()
    owner = uuid.uuid4()
    pause_capture(owner, guard, max_presign_ttl=1, transfer_bound=1)
    guard.assert_valid.side_effect = RuntimeError("lost database guard")
    with pytest.raises(RuntimeError):
        finish_capture(owner, guard)
    state.refresh_from_db()
    assert state.paused_by == owner


def test_only_drained_owner_can_resume(state):
    guard = Mock(unsafe=True)  # the guard API is assert_valid()
    owner = uuid.uuid4()
    pause_capture(owner, guard, max_presign_ttl=1, transfer_bound=1)
    ManagedCaptureState.objects.filter(pk=1).update(drain_until=timezone.now() - timedelta(seconds=1))
    with pytest.raises(WriterFenceError):
        finish_capture(uuid.uuid4(), guard)
    finish_capture(owner, guard)
    with writer_boundary("presign") as boundary:
        boundary.assert_valid()
