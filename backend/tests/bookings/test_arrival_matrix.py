"""Exercise real arrival/correction and named lifecycle workflows together."""
from datetime import timedelta
import pytest
from django.db import DatabaseError, transaction
from apps.audit.models import AuditLog
from apps.bookings import services
from apps.bookings.models import Booking, BookingCheckInEvent
from apps.bookings.exceptions import BookingInvalidTransition
from apps.bookings.services_arrival import confirm_arrival, reverse_arrival
from apps.bookings.services_reschedule import reschedule_booking
from tests.bookings.arrival_helpers import world, clock

pytestmark = pytest.mark.django_db


def test_resolve_does_not_arrive_and_duplicate_arrival_is_idempotent(monkeypatch):
    from apps.bookings.services_arrival import resolve_booking
    w = world(); clock(monkeypatch, w.booking.starts_at)
    resolve_booking(w.resource, w.credential, actor=w.scanner)
    assert not BookingCheckInEvent.objects.exists()
    first = confirm_arrival(w.resource, w.credential, actor=w.scanner)
    again = confirm_arrival(w.resource, w.credential, actor=w.scanner)
    assert first.arrived_at == again.arrived_at
    assert again.status == "confirmed" and again.calendar_sequence == 0
    assert BookingCheckInEvent.objects.count() == 1
    assert AuditLog.objects.filter(action="booking.arrival_confirmed").count() == 1


@pytest.mark.parametrize("offset,accepted", [(-1800,True),(-1800.001,False),(3600,True),(3600.001,False)])
def test_inclusive_window_edges(monkeypatch, offset, accepted):
    w = world(); clock(monkeypatch, w.booking.starts_at + timedelta(seconds=offset))
    if accepted:
        assert confirm_arrival(w.resource, w.credential, actor=w.scanner).arrived_at
    else:
        with pytest.raises(BookingInvalidTransition): confirm_arrival(w.resource, w.credential, actor=w.scanner)
        assert not BookingCheckInEvent.objects.exists()


@pytest.mark.parametrize("status", ["pending","rejected","cancelled","completed","no_show"])
def test_only_confirmed_accepts_new_or_reinstated_arrival(monkeypatch, status):
    w = world(); clock(monkeypatch, w.booking.starts_at)
    Booking.objects.filter(pk=w.booking.pk).update(status=status)
    with pytest.raises(BookingInvalidTransition): confirm_arrival(w.resource, w.credential, actor=w.scanner)
    assert not BookingCheckInEvent.objects.exists()


@pytest.mark.parametrize("operation", ["cancel","move","no_show"])
def test_active_arrival_refuses_mutations_without_any_side_effect(monkeypatch, operation):
    w = world(); clock(monkeypatch, w.booking.starts_at - timedelta(minutes=5))
    arrived = confirm_arrival(w.resource, w.credential, actor=w.scanner)
    before = (arrived.status, arrived.starts_at, arrived.ends_at, arrived.calendar_sequence, arrived.checkin_token, arrived.arrived_at)
    count = AuditLog.objects.count()
    if operation == "no_show": clock(monkeypatch, arrived.ends_at)
    with pytest.raises(BookingInvalidTransition):
        if operation == "cancel": services.cancel_booking(arrived, actor=w.manager)
        elif operation == "no_show": services.mark_no_show(arrived, actor=w.manager)
        else: reschedule_booking(arrived, actor=w.owner, starts_at=arrived.starts_at + timedelta(days=1), ends_at=arrived.ends_at + timedelta(days=1))
    arrived.refresh_from_db()
    assert before == (arrived.status, arrived.starts_at, arrived.ends_at, arrived.calendar_sequence, arrived.checkin_token, arrived.arrived_at)
    assert AuditLog.objects.count() == count and BookingCheckInEvent.objects.count() == 1


def test_reversal_then_no_show_and_terminal_refusal(monkeypatch):
    w = world(); clock(monkeypatch, w.booking.starts_at)
    confirm_arrival(w.resource, w.credential, actor=w.scanner)
    reverse_arrival(w.booking, actor=w.scanner)
    with pytest.raises(BookingInvalidTransition): services.mark_no_show(w.booking, actor=w.manager)
    clock(monkeypatch, w.booking.ends_at)
    result = services.mark_no_show(w.booking, actor=w.manager)
    assert result.status == "no_show" and result.arrived_at is None
    assert list(BookingCheckInEvent.objects.values_list("action", flat=True)) == ["arrived","reversed"]
    with pytest.raises(BookingInvalidTransition): confirm_arrival(w.resource, w.credential, actor=w.scanner)


@pytest.mark.parametrize("arrived", [False, True])
def test_completion_is_independent_and_post_completion_reversal_never_reopens(monkeypatch, arrived):
    w = world(); clock(monkeypatch, w.booking.starts_at)
    if arrived: confirm_arrival(w.resource, w.credential, actor=w.scanner)
    with pytest.raises(BookingInvalidTransition): services.complete_booking(w.booking, actor=w.manager)
    clock(monkeypatch, w.booking.ends_at)
    completed = services.complete_booking(w.booking, actor=w.manager)
    assert completed.status == "completed" and bool(completed.arrived_at) == arrived
    if arrived:
        corrected = reverse_arrival(completed, actor=w.scanner)
        assert corrected.status == "completed" and corrected.arrived_at is None
        assert corrected.calendar_sequence == completed.calendar_sequence
    with pytest.raises(BookingInvalidTransition): confirm_arrival(w.resource, w.credential, actor=w.scanner)
    with pytest.raises(BookingInvalidTransition): services.cancel_booking(completed, actor=w.manager)
    with pytest.raises(BookingInvalidTransition): reschedule_booking(completed, actor=w.owner, starts_at=completed.starts_at + timedelta(days=1), ends_at=completed.ends_at + timedelta(days=1))


def test_reversal_then_member_move_rotates_qr_but_preserves_history_and_identity(monkeypatch):
    from rest_framework.exceptions import NotFound
    w = world(); clock(monkeypatch, w.booking.starts_at - timedelta(minutes=15))
    confirm_arrival(w.resource, w.credential, actor=w.scanner)
    reversed_booking = reverse_arrival(w.booking, actor=w.scanner)
    moved = reschedule_booking(reversed_booking, actor=w.owner, starts_at=w.booking.starts_at + timedelta(days=1), ends_at=w.booking.ends_at + timedelta(days=1))
    assert moved.checkin_token != w.booking.checkin_token and moved.public_token == w.booking.public_token
    assert moved.arrived_at is None and moved.calendar_sequence == 1
    assert BookingCheckInEvent.objects.count() == 2
    with pytest.raises(NotFound): confirm_arrival(w.resource, w.credential, actor=w.scanner)


def test_history_is_immutable_even_through_queryset_update_and_delete(monkeypatch):
    w = world(); clock(monkeypatch, w.booking.starts_at)
    confirm_arrival(w.resource, w.credential, actor=w.scanner)
    row = BookingCheckInEvent.objects.get()
    with pytest.raises(RuntimeError): row.save()
    with pytest.raises(RuntimeError): row.delete()
    for mutation in (lambda: BookingCheckInEvent.objects.update(action="reversed"), lambda: BookingCheckInEvent.objects.all().delete()):
        with pytest.raises(DatabaseError), transaction.atomic(): mutation()
    assert BookingCheckInEvent.objects.get().action == "arrived"


@pytest.mark.parametrize("state", ["rejected","cancelled","completed","no_show"])
def test_mutation_guard_blocks_terminal_time_edits_even_into_future(monkeypatch, state):
    from apps.bookings.services_bookings import _locked_booking
    w = world(); Booking.objects.filter(pk=w.booking.pk).update(status=state)
    with pytest.raises(BookingInvalidTransition), transaction.atomic():
        space, row = _locked_booking(w.booking); row.space = space
        row.starts_at += timedelta(days=1); row.ends_at += timedelta(days=1)
        row.save(update_fields=["starts_at", "ends_at"])
    w.booking.refresh_from_db()
    assert w.booking.status == state and w.booking.calendar_sequence == 0


@pytest.mark.parametrize("offset", [0, -1])
def test_old_cutoff_equality_and_started_time_edits_refuse(monkeypatch, offset):
    w = world(); clock(monkeypatch,w.booking.starts_at + timedelta(seconds=-offset))
    before = w.booking.starts_at
    with pytest.raises(BookingInvalidTransition): reschedule_booking(w.booking,actor=w.owner,starts_at=before+timedelta(days=1),ends_at=w.booking.ends_at+timedelta(days=1))
    w.booking.refresh_from_db(); assert w.booking.starts_at == before and w.booking.calendar_sequence == 0


def test_guard_checks_new_cutoff_at_the_same_server_snapshot(monkeypatch):
    from apps.bookings.services_bookings import _locked_booking
    w = world(); now=w.booking.starts_at-timedelta(hours=4); clock(monkeypatch,now)
    w.resource.cancellation_cutoff_hours=2; w.resource.save(update_fields=["cancellation_cutoff_hours"])
    with pytest.raises(BookingInvalidTransition), transaction.atomic():
        space,row=_locked_booking(w.booking); row.space=space; row._arrival_clock=now
        row.starts_at=now+timedelta(hours=2); row.ends_at=now+timedelta(hours=3)
        row.save(update_fields=["starts_at","ends_at"])
    w.booking.refresh_from_db(); assert w.booking.calendar_sequence == 0


def test_no_show_without_arrival_is_still_a_manual_ended_transition(monkeypatch):
    w=world(); clock(monkeypatch,w.booking.ends_at)
    result=services.mark_no_show(w.booking,actor=w.manager)
    assert result.status == "no_show" and result.arrived_at is None
    assert not BookingCheckInEvent.objects.exists()


def test_duplicate_arrival_outside_window_refuses_even_if_already_arrived(monkeypatch):
    w=world(); clock(monkeypatch,w.booking.starts_at)
    confirm_arrival(w.resource,w.credential,actor=w.scanner)
    clock(monkeypatch,w.booking.ends_at+timedelta(microseconds=1))
    with pytest.raises(BookingInvalidTransition): confirm_arrival(w.resource,w.credential,actor=w.scanner)
    assert BookingCheckInEvent.objects.count() == 1
