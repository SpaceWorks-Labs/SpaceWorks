"""BK-B staff tools and BK-C arrival share one locked booking lifecycle."""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.bookings import services
from apps.bookings.exceptions import BookingInvalidTransition
from apps.bookings.models import Booking, BookingCheckInEvent
from apps.bookings.services_arrival import confirm_arrival, qr_value, resolve_booking, reverse_arrival
from apps.bookings.services_reschedule import reschedule_booking
from tests.bookings.test_staff_tools_helpers import NOW, snapshot, world

pytestmark = pytest.mark.django_db


def arrival_world(monkeypatch, **kwargs):
    w = world(monkeypatch, **kwargs)
    w.tenant.enabled_features += ["bookings.confirmations", "bookings.checkin"]
    w.tenant.save(update_fields=["enabled_features"])
    return w


def clock(monkeypatch, instant):
    monkeypatch.setattr(timezone, "now", lambda: instant)


@pytest.mark.parametrize("seconds,allowed", [(-1801, False), (-1800, True), (0, True), (3600, True), (3601, False)])
def test_arrival_window_is_inclusive_and_duplicate_arrival_is_idempotent(monkeypatch, seconds, allowed):
    w = arrival_world(monkeypatch)
    clock(monkeypatch, w.row.starts_at + timedelta(seconds=seconds))
    before = snapshot(w)
    if not allowed:
        with pytest.raises(BookingInvalidTransition):
            confirm_arrival(w.resource, qr_value(w.row), actor=w.actor)
        assert snapshot(w) == before
        return
    arrived = confirm_arrival(w.resource, qr_value(w.row), actor=w.actor)
    assert arrived.status == "confirmed" and arrived.arrived_at == timezone.now()
    after = snapshot(w)
    confirm_arrival(w.resource, qr_value(arrived), actor=w.actor)
    assert snapshot(w) == after
    assert BookingCheckInEvent.objects.filter(booking=w.row, action="arrived").count() == 1


@pytest.mark.parametrize("status", ["pending", "cancelled", "completed", "rejected", "no_show"])
def test_nonconfirmed_bookings_refuse_arrival(monkeypatch, status):
    w = arrival_world(monkeypatch)
    Booking.objects.filter(pk=w.row.pk).update(status=status)
    clock(monkeypatch, w.row.starts_at)
    before = snapshot(w)
    with pytest.raises(BookingInvalidTransition):
        confirm_arrival(w.resource, qr_value(w.row), actor=w.actor)
    assert snapshot(w) == before
    assert not BookingCheckInEvent.objects.exists()


@pytest.mark.parametrize("operation", ["details", "staff_time", "member_time", "cancel", "no_show"])
def test_arrived_booking_refuses_edits_cancellation_and_no_show(monkeypatch, operation):
    w = arrival_world(monkeypatch)
    clock(monkeypatch, w.row.starts_at - timedelta(minutes=15))
    confirm_arrival(w.resource, qr_value(w.row), actor=w.actor)
    if operation == "no_show":
        clock(monkeypatch, w.row.ends_at)
    before = snapshot(w)
    history = list(BookingCheckInEvent.objects.values())
    with pytest.raises(BookingInvalidTransition):
        if operation == "details":
            services.edit_booking_details(w.row, actor=w.grantee, note="Changed")
        elif operation in ("staff_time", "member_time"):
            move = services.edit_booking_time if operation == "staff_time" else reschedule_booking
            move(w.row, actor=w.grantee if operation == "staff_time" else w.member,
                 starts_at=w.row.starts_at + timedelta(days=1), ends_at=w.row.ends_at + timedelta(days=1))
        elif operation == "cancel":
            services.cancel_booking(w.row, actor=w.grantee)
        else:
            services.mark_no_show(w.row, actor=w.grantee)
    assert snapshot(w) == before
    assert list(BookingCheckInEvent.objects.values()) == history


@pytest.mark.parametrize("status", ["cancelled", "completed", "rejected", "no_show"])
def test_terminal_booking_detail_edits_are_refused(monkeypatch, status):
    w = arrival_world(monkeypatch)
    Booking.objects.filter(pk=w.row.pk).update(status=status)
    before = snapshot(w)
    with pytest.raises(BookingInvalidTransition):
        services.edit_booking_details(w.row, actor=w.grantee, note="Changed")
    assert snapshot(w) == before


@pytest.mark.parametrize("arrived", [False, True])
def test_completion_keeps_arrival_and_reversal_does_not_reopen(monkeypatch, arrived):
    w = arrival_world(monkeypatch)
    if arrived:
        clock(monkeypatch, w.row.starts_at)
        confirm_arrival(w.resource, qr_value(w.row), actor=w.actor)
    clock(monkeypatch, w.row.ends_at - timedelta(microseconds=1))
    with pytest.raises(BookingInvalidTransition):
        services.complete_booking(w.row, actor=w.grantee)
    clock(monkeypatch, w.row.ends_at)
    completed = services.complete_booking(w.row, actor=w.grantee)
    assert completed.status == "completed"
    assert (completed.arrived_at is not None) == arrived
    if arrived:
        corrected = reverse_arrival(completed, actor=w.actor)
        assert corrected.status == "completed" and corrected.arrived_at is None
        assert list(corrected.check_in_events.values_list("action", flat=True)) == ["arrived", "reversed"]
        with pytest.raises(BookingInvalidTransition):
            confirm_arrival(w.resource, qr_value(corrected), actor=w.actor)


def test_no_show_requires_end_and_reversal(monkeypatch):
    w = arrival_world(monkeypatch)
    clock(monkeypatch, w.row.starts_at)
    arrived = confirm_arrival(w.resource, qr_value(w.row), actor=w.actor)
    reverse_arrival(arrived, actor=w.actor)
    with pytest.raises(BookingInvalidTransition):
        services.mark_no_show(w.row, actor=w.grantee)
    clock(monkeypatch, w.row.ends_at)
    assert services.mark_no_show(w.row, actor=w.grantee).status == "no_show"


def test_staff_move_cancel_and_exact_undo_rotate_credentials_without_losing_provenance(monkeypatch):
    w = arrival_world(monkeypatch)
    original = qr_value(w.row)
    moved = services.edit_booking_time(w.row, actor=w.grantee,
                                      starts_at=NOW + timedelta(days=3), ends_at=NOW + timedelta(days=3, hours=1))
    assert qr_value(moved) != original and moved.calendar_updated_at == NOW
    moved_qr = qr_value(moved)
    cancelled = services.cancel_booking(moved, actor=w.grantee)
    assert cancelled.cancelled_at == NOW and cancelled.status_before_cancel == "confirmed"
    cancelled_qr = qr_value(cancelled)
    restored = services.restore_booking(cancelled, actor=w.grantee)
    assert restored.status == "confirmed" and restored.cancelled_at is None
    assert restored.status_before_cancel == "" and restored.arrived_at is None
    assert len({original, moved_qr, cancelled_qr, qr_value(restored)}) == 4
    for credential in (original, moved_qr, cancelled_qr):
        with pytest.raises(NotFound):
            resolve_booking(w.resource, credential, actor=w.actor)
