"""Real PostgreSQL maker/event inversion regression for admitted runtime."""
from conftest import _BoundedThreadPoolExecutor as ThreadPoolExecutor
from datetime import timedelta
from threading import Event as ThreadEvent
from uuid import uuid4

import pytest
from django.db import close_old_connections, transaction, connection, connections
from django.utils import timezone

from apps.bookings.models import BookableSpace, Booking
from apps.events import booking_decision_service as service
from apps.events.models import Event
from apps.events.models_booking_decision import EventBookingDecision
from apps.encryption.preparation import prepare_tenants
from apps.makerspaces.models import Makerspace
from tests.encryption.conftest import enabled_encryption
from tests.events.orders_helpers import l6_space, make_staff, verified

pytestmark = pytest.mark.django_db(transaction=True)


def test_maker_lock_conflict_unwinds_entire_decision_without_partial_write():
    maker = l6_space("decision-maker-lock")
    maker.enabled_modules = sorted(set(maker.enabled_modules) | {"bookings"})
    maker.save(update_fields=["enabled_modules"])
    staff, member = make_staff(maker), verified("decision-maker-lock-member")
    start = timezone.now() + timedelta(days=1)
    event = Event.objects.create(makerspace=maker, title="Event", starts_at=start,
                                 ends_at=start + timedelta(hours=1), registration_audience="accounts", status="draft")
    room = BookableSpace.objects.create(makerspace=maker, name="Room")
    booking = Booking.objects.create(space=room, member=member, name="Member", email=member.email,
                                     starts_at=start, ends_at=start + timedelta(hours=1))
    operation = uuid4()
    kwargs = dict(booking_id=booking.pk, operation_id=operation, expected_generation=None, expected_revision=0,
                  expected_events_epoch=maker.loan_context_generations["events"],
                  expected_bookings_epoch=maker.loan_context_generations["bookings"])

    prepared, decide = ThreadEvent(), ThreadEvent()

    def writer():
        close_old_connections()
        try:
            if connection.vendor == "postgresql":
                with connection.cursor() as cursor:
                    # Exceed the 10-second rendezvous; the future and pool still bound completion.
                    cursor.execute("SET lock_timeout = '20s'")
            # Even an existing key takes a maker lock. Prepare in this worker's context
            # before the holder locks it, so the real boundary reaches FOR UPDATE NOWAIT.
            with prepare_tenants((maker.pk,)):
                prepared.set()
                assert decide.wait(timeout=10)
                with pytest.raises(service.DecisionConflict) as error:
                    service.create_decision(staff, maker, event.pk, **kwargs)
                assert error.value.status_code == 409
                assert error.value.detail == {
                    "code": "lock_busy", "detail": "Booking decision cannot be applied.",
                }
                return str(error.value.detail["code"])
        finally:
            connections.close_all()

    with enabled_encryption(), ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(writer)
        try:
            assert prepared.wait(timeout=10)
            with transaction.atomic():
                # NO KEY UPDATE conflicts with FOR UPDATE NOWAIT but permits FK key-shares.
                Makerspace.objects.select_for_update(no_key=True).get(pk=maker.pk)
                decide.set()
                assert future.result(timeout=10) == "lock_busy"
        finally:
            decide.set()
        assert not EventBookingDecision.objects.filter(makerspace=maker, operation_id=operation).exists()
