"""A real psycopg2 NOWAIT failure remains a typed booking decision conflict."""
from datetime import timedelta
from uuid import uuid4

import psycopg2
import pytest
from django.db import connection
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.bookings.models import BookableSpace, Booking
from apps.events import booking_decision_service as service
from apps.events.models import Event
from apps.events.models_booking_decision import EventBookingDecision
from tests.encryption.conftest import enabled_encryption
from tests.events.orders_helpers import l6_space, make_staff, verified

pytestmark = pytest.mark.django_db(transaction=True)


def test_psycopg2_held_booking_lock_returns_409_lock_busy_and_can_retry():
    maker = l6_space("sqlstate-booking-lock")
    maker.enabled_modules = sorted(set(maker.enabled_modules) | {"bookings"})
    maker.save(update_fields=["enabled_modules"])
    actor, member = make_staff(maker), verified("sqlstate-booking-borrower")
    start = timezone.now() + timedelta(days=1)
    event = Event.objects.create(makerspace=maker, title="Workshop", starts_at=start,
        ends_at=start + timedelta(hours=1), registration_audience="accounts", status="draft")
    room = BookableSpace.objects.create(makerspace=maker, name="Room")
    booking = Booking.objects.create(space=room, member=member, name="Borrower", email=member.email,
        starts_at=start, ends_at=start + timedelta(hours=1))
    kwargs = dict(booking_id=booking.pk, operation_id=uuid4(), expected_generation=None, expected_revision=0,
        expected_events_epoch=maker.loan_context_generations["events"],
        expected_bookings_epoch=maker.loan_context_generations["bookings"])
    with enabled_encryption():
        # Use the active test database without Django's unregistered-alias signals.
        db = connection.settings_dict
        holder = psycopg2.connect(
            dbname=db["NAME"], user=db["USER"], password=db["PASSWORD"],
            host=db["HOST"], port=db["PORT"], connect_timeout=5,
        )
        try:
            holder.autocommit = False
            with holder.cursor() as cursor:
                cursor.execute("SET LOCAL lock_timeout = '2s'")
                cursor.execute("SET LOCAL statement_timeout = '5s'")
                cursor.execute("SELECT id FROM bookings_booking WHERE id = %s FOR NO KEY UPDATE", [booking.pk])
                assert cursor.fetchone() == (booking.pk,)
            with pytest.raises(service.DecisionConflict) as caught:
                service.create_decision(actor, maker, event.pk, **kwargs)
            assert caught.value.status_code == 409
            assert caught.value.detail["code"] == "lock_busy"
            driver = caught.value.__context__.__cause__
            assert isinstance(driver, psycopg2.errors.LockNotAvailable)
            assert driver.pgcode == "55P03"
            assert EventBookingDecision.objects.filter(makerspace=maker).count() == 0
            assert AuditLog.objects.filter(makerspace=maker, action="event.booking_decision_linked").count() == 0
        finally:
            # Release the extra session before the test database's transactional flush.
            holder.close()

        row, replay = service.create_decision(actor, maker, event.pk, **kwargs)
    assert replay is False
    assert row.booking_id == booking.pk
    assert EventBookingDecision.objects.filter(makerspace=maker).count() == 1
    assert AuditLog.objects.filter(makerspace=maker, action="event.booking_decision_linked").count() == 1
