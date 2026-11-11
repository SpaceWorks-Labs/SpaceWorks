"""Independent PostgreSQL connections contend at the shared resource lock."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import close_old_connections, connection, connections

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.bookings import services
from apps.bookings.exceptions import BookingConflict
from apps.bookings.models import BookableSpace, Booking
from apps.operations.cancellation_restore import RestoreRefused
from tests.bookings.test_staff_tools_helpers import world

pytestmark = pytest.mark.django_db(transaction=True)


def race(w, operations):
    gate = Barrier(2)
    def worker(operation):
        close_old_connections()
        try:
            # Open the physical connection before the rendezvous, proving these are
            # competing sessions rather than two sequential calls on one connection.
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                backend_id = cursor.fetchone()[0]
            row = Booking.objects.get(pk=w.row.pk)
            actor = User.objects.get(pk=w.actor.pk)
            gate.wait(timeout=10)
            try:
                if operation == "restore":
                    services.restore_booking(row, actor=actor)
                    result = "restored"
                else:
                    services.create_booking(
                        BookableSpace.objects.get(pk=w.resource.pk), member=User.objects.get(pk=w.member.pk),
                        starts_at=row.starts_at, ends_at=row.ends_at, custom_answers={"purpose": "Racing rebooking"},
                    )
                    result = "rebooked"
            except BookingConflict:
                result = "conflict"
            except RestoreRefused as error:
                result = str(error.detail["code"])
            return backend_id, result
        finally:
            connections["default"].close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker, operation) for operation in operations]
        results = [future.result(timeout=40) for future in futures]
    assert len({backend_id for backend_id, result in results}) == 2
    return sorted(result for backend_id, result in results)


def test_undo_versus_rebook_has_one_confirmed_window_and_one_winner(monkeypatch):
    w = world(monkeypatch)
    w.row = services.cancel_booking(w.row, actor=w.actor)
    results = race(w, ["restore", "rebook"])
    assert results in (["conflict", "restored"], ["conflict", "rebooked"])
    assert Booking.objects.filter(space=w.resource, status="confirmed").count() == 1
    w.row.refresh_from_db()
    assert w.row.status == ("confirmed" if "restored" in results else "cancelled")
    assert AuditLog.objects.filter(action="booking.restored", makerspace=w.tenant).count() == int("restored" in results)


def test_two_simultaneous_undo_attempts_have_one_calendar_increment(monkeypatch):
    w = world(monkeypatch)
    w.row = services.cancel_booking(w.row, actor=w.actor)
    sequence, identity = w.row.calendar_sequence, w.row.public_token
    assert race(w, ["restore", "restore"]) == ["not_cancelled", "restored"]
    w.row.refresh_from_db()
    assert w.row.status == "confirmed" and w.row.calendar_sequence == sequence + 1
    assert w.row.public_token == identity and w.row.cancelled_at is None
    assert AuditLog.objects.filter(action="booking.restored", makerspace=w.tenant).count() == 1
