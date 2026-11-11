"""Every arrival/lifecycle race uses independent physical PG sessions."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
import pytest
from django.db import close_old_connections, connection, connections
from rest_framework.exceptions import NotFound
from apps.accounts.models import User
from apps.bookings import services
from apps.bookings.models import Booking, BookingCheckInEvent, BookableSpace
from apps.bookings.exceptions import BookingInvalidTransition
from apps.bookings.services_arrival import confirm_arrival, reverse_arrival
from apps.bookings.services_reschedule import reschedule_booking
from tests.bookings.arrival_helpers import world, clock

pytestmark = pytest.mark.django_db(transaction=True)


def race(w, operations):
    barrier = Barrier(2)
    def worker(operation):
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                backend = cursor.fetchone()[0]
            booking = Booking.objects.get(pk=w.booking.pk)
            actor = User.objects.get(pk=w.manager.pk)
            scanner = User.objects.get(pk=w.scanner.pk)
            barrier.wait(timeout=10)
            try:
                if operation == "arrive": confirm_arrival(BookableSpace.objects.get(pk=w.resource.pk), w.credential, actor=scanner)
                elif operation == "reverse": reverse_arrival(booking, actor=scanner)
                elif operation == "approve": services.approve_booking(booking, actor=actor)
                elif operation == "reject": services.reject_booking(booking, actor=actor, reason="Resource unavailable")
                elif operation == "cancel": services.cancel_booking(booking, actor=actor)
                elif operation == "complete": services.complete_booking(booking, actor=actor)
                elif operation == "no_show": services.mark_no_show(booking, actor=actor)
                else: reschedule_booking(booking, actor=User.objects.get(pk=w.owner.pk), starts_at=booking.starts_at + timedelta(days=1), ends_at=booking.ends_at + timedelta(days=1))
                result = "ok"
            except (BookingInvalidTransition, NotFound): result = "refused"
            return backend, result
        finally: connections["default"].close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker, operation) for operation in operations]
        results = [future.result(timeout=40) for future in futures]
    assert len({pid for pid, result in results}) == 2
    w.booking.refresh_from_db()
    return [result for pid, result in results]


def test_duplicate_arrival_has_one_history_row(monkeypatch):
    w = world(); clock(monkeypatch, w.booking.starts_at)
    assert race(w,["arrive","arrive"]) == ["ok","ok"]
    assert w.booking.arrived_at and BookingCheckInEvent.objects.count() == 1


@pytest.mark.parametrize("operation", ["cancel","move","no_show","complete"])
def test_arrival_versus_each_transition_rechecks_locked_state(monkeypatch, operation):
    w = world(); clock(monkeypatch, w.booking.ends_at if operation in ("no_show","complete") else w.booking.starts_at - timedelta(minutes=10))
    result = race(w,["arrive",operation])
    assert "ok" in result
    if operation == "complete":
        assert w.booking.status == "completed"
        assert bool(w.booking.arrived_at) == (result[0] == "ok")
    elif operation == "move":
        assert bool(w.booking.arrived_at) != (result[1] == "ok")
        assert (w.booking.calendar_sequence == 1) == (result[1] == "ok")
    elif w.booking.status in ("cancelled","no_show"):
        assert w.booking.arrived_at is None and result[0] == "refused"
    else:
        assert w.booking.status == "confirmed" and w.booking.arrived_at and result[1] == "refused"
    assert BookingCheckInEvent.objects.filter(action="arrived").count() == int(result[0] == "ok")


@pytest.mark.parametrize("operation", ["cancel","move","no_show","complete"])
def test_reversal_against_each_transition_never_reopens_history(monkeypatch, operation):
    w = world(); clock(monkeypatch, w.booking.starts_at - timedelta(minutes=10))
    confirm_arrival(w.resource,w.credential,actor=w.scanner)
    clock(monkeypatch,w.booking.ends_at if operation in ("no_show","complete") else w.booking.starts_at - timedelta(minutes=5))
    result = race(w,["reverse",operation])
    assert result[0] == "ok" and w.booking.arrived_at is None
    assert list(BookingCheckInEvent.objects.values_list("action",flat=True)) == ["arrived","reversed"]
    if operation == "complete": assert w.booking.status == "completed" and result[1] == "ok"
    if operation == "move": assert w.booking.status == "confirmed"


def test_arrival_and_reversal_projection_matches_last_append(monkeypatch):
    w = world(); clock(monkeypatch,w.booking.starts_at)
    confirm_arrival(w.resource,w.credential,actor=w.scanner)
    assert race(w,["arrive","reverse"]) == ["ok","ok"]
    last = BookingCheckInEvent.objects.order_by("-pk").first()
    assert bool(w.booking.arrived_at) == (last.action == "arrived")


@pytest.mark.parametrize("operation",["approve","reject"])
def test_pending_decision_races_cannot_arrive_in_pending_or_rejected_state(monkeypatch,operation):
    w=world(); Booking.objects.filter(pk=w.booking.pk).update(status="pending")
    clock(monkeypatch,w.booking.starts_at-timedelta(minutes=10))
    results=race(w,["arrive",operation])
    assert results[1] == "ok"
    if operation == "reject":
        assert w.booking.status == "rejected" and w.booking.arrived_at is None
        assert results[0] == "refused"
    else:
        assert w.booking.status == "confirmed"
        assert bool(w.booking.arrived_at) == (results[0] == "ok")
