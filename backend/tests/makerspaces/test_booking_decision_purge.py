"""Exact decision purge exception, scoped to one maker; unrun PostgreSQL tests."""
from datetime import timedelta
from uuid import uuid4

import pytest
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.utils import timezone

from apps.bookings.models import BookableSpace, Booking
from apps.events.models import Event
from apps.events.models_booking_decision import EventBookingDecision
from apps.makerspaces.booking_decision_purge import detach_booking_decisions, delete_booking_decisions
from tests.events.orders_helpers import l6_space, verified

pytestmark = pytest.mark.django_db(transaction=True)


def _decision(slug):
    maker = l6_space(slug)
    actor = verified(slug + "-actor")
    start = timezone.now() + timedelta(days=1)
    event = Event.objects.create(makerspace=maker, title="Event", starts_at=start,
                                 ends_at=start + timedelta(hours=1), registration_audience="accounts", status="draft")
    room = BookableSpace.objects.create(makerspace=maker, name="Room")
    booking = Booking.objects.create(space=room, member=actor, name="Member", email=actor.email,
                                     starts_at=start, ends_at=start + timedelta(hours=1))
    row = EventBookingDecision.objects.create(makerspace=maker, event=event, booking=booking,
                                               creator=actor, operation_id=uuid4(), intent={"version": 1})
    return maker, row


def test_only_fenced_tenant_purge_can_detach_or_delete():
    maker, row = _decision("decision-purge-one")
    other, other_row = _decision("decision-purge-two")
    with pytest.raises(DatabaseError), transaction.atomic():
        EventBookingDecision.objects.filter(pk=row.pk).update(booking=None)
    with transaction.atomic():
        assert detach_booking_decisions(maker) == 1
    row.refresh_from_db(); other_row.refresh_from_db()
    assert row.booking_id is None and other_row.booking_id is not None
    with pytest.raises(DatabaseError), transaction.atomic():
        # The model's own delete() refuses first (ValidationError); a queryset delete skips it,
        # so this exercises the database guard that only the fenced purge may lift.
        EventBookingDecision.objects.filter(pk=row.pk).delete()
    with pytest.raises(ValidationError):
        row.delete()
    with transaction.atomic():
        assert delete_booking_decisions(maker) == 1
    assert not EventBookingDecision.objects.filter(pk=row.pk).exists()
    assert EventBookingDecision.objects.filter(pk=other_row.pk, makerspace=other).exists()


def test_database_rejects_cross_maker_event_or_booking_on_insert():
    maker, row = _decision("decision-owner-one")
    other, foreign = _decision("decision-owner-two")
    with pytest.raises(DatabaseError), transaction.atomic():
        EventBookingDecision.objects.create(makerspace=maker, event=foreign.event, creator=row.creator,
                                            operation_id=uuid4(), intent={"version": 1})
    new_event = Event.objects.create(makerspace=maker, title="Second", starts_at=row.event.starts_at,
                                     ends_at=row.event.ends_at, registration_audience="accounts", status="draft")
    with pytest.raises(DatabaseError), transaction.atomic():
        EventBookingDecision.objects.create(makerspace=maker, event=new_event, booking=foreign.booking,
                                            creator=row.creator, operation_id=uuid4(), intent={"version": 1})
    assert not EventBookingDecision.objects.filter(event=new_event).exists()
