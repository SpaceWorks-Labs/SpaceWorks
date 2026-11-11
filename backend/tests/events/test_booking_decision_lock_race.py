"""Real PostgreSQL maker/event inversion regression for admitted runtime."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4

import pytest
from django.db import close_old_connections, transaction
from django.utils import timezone

from apps.bookings.models import BookableSpace, Booking
from apps.events import booking_decision_service as service
from apps.events.models import Event
from apps.events.models_booking_decision import EventBookingDecision
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

    def writer():
        close_old_connections()
        try:
            with pytest.raises(service.DecisionConflict) as error:
                service.create_decision(staff, maker, event.pk, **kwargs)
            return str(error.value.detail["code"])
        finally:
            close_old_connections()

    with enabled_encryption(), ThreadPoolExecutor(max_workers=1) as executor:
        with transaction.atomic():
            Makerspace.objects.select_for_update().get(pk=maker.pk)
            future = executor.submit(writer)
            assert future.result(timeout=10) == "lock_busy"
        assert not EventBookingDecision.objects.filter(makerspace=maker, operation_id=operation).exists()
