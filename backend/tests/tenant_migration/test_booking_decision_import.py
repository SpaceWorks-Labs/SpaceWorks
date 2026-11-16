"""Retained booking-decision import proof and sticky history; unrun."""
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.bookings.models import BookableSpace, Booking
from apps.events.models import Event
from apps.separability.booking_decision_intent import canonical_intent
from apps.tenant_migration import booking_decision_import as decision_import
from apps.tenant_migration.insertion_errors import ArchiveFormatError
from tests.events.orders_helpers import l6_space, verified

pytestmark = pytest.mark.django_db


class IdentityMap:
    def lookup(self, model, source_pk):
        return source_pk


class References:
    def __init__(self, missing=()):
        self.missing = set(missing)

    def equipment_materialized(self, label, source, mapped):
        return label not in self.missing and source == mapped

    def equipment_identity_resolved(self, source, mapped):
        return source == mapped


def test_unretained_booking_stays_unavailable_even_after_identifier_reappears():
    maker = l6_space("decision-import-sticky")
    actor = verified("decision-import-actor")
    start = timezone.now() + timedelta(days=1)
    event = Event.objects.create(makerspace=maker, title="Event", starts_at=start,
                                 ends_at=start + timedelta(hours=1), registration_audience="accounts", status="draft")
    room = BookableSpace.objects.create(makerspace=maker, name="Room")
    booking = Booking.objects.create(space=room, member=actor, name="Member", email=actor.email,
                                     starts_at=start, ends_at=start + timedelta(hours=1))
    intent = canonical_intent(makerspace_id=maker.pk, event_id=event.pk, booking_id=booking.pk, creator_id=actor.pk)
    row = {"makerspace_id": maker.pk, "event_id": event.pk, "booking_id": booking.pk,
           "creator_id": actor.pk, "generation": uuid4(), "intent_version": 1, "billing_owner": "booking", "revision": 1, "intent": intent}
    job = SimpleNamespace(source_makerspace_id=maker.pk)
    sticky = decision_import.prepare(row, job=job, pk_map=IdentityMap(), references=References({"bookings.Booking"}), target=maker)
    assert sticky and row["booking_id"] is None
    decision_import.finish(row, sticky)
    assert row["intent"] == {"version": 1, "unavailable": True}
    assert decision_import.prepare(row, job=job, pk_map=IdentityMap(), references=References(), target=maker)
    decision_import.finish(row, True)
    assert row["booking_id"] is None and row["intent"]["unavailable"] is True


def test_missing_required_event_is_refused_even_with_reserved_mapping():
    maker = l6_space("decision-import-event")
    actor = verified("decision-import-required-actor")
    start = timezone.now() + timedelta(days=1)
    event = Event.objects.create(makerspace=maker, title="Event", starts_at=start,
                                 ends_at=start + timedelta(hours=1), registration_audience="accounts", status="draft")
    row = {"makerspace_id": maker.pk, "event_id": event.pk, "booking_id": None,
           "creator_id": actor.pk, "generation": uuid4(), "intent_version": 1, "billing_owner": "booking", "revision": 1,
           "intent": {"version": 1, "unavailable": True}}
    with pytest.raises(ArchiveFormatError):
        decision_import.prepare(row, job=SimpleNamespace(source_makerspace_id=maker.pk),
                                pk_map=IdentityMap(), references=References({"events.Event"}), target=maker)


def test_purged_mapped_creator_is_unavailable_not_rebound_to_live_replay():
    maker = l6_space("decision-import-purged-creator")
    actor = verified("decision-import-purged-actor")
    start = timezone.now() + timedelta(days=1)
    event = Event.objects.create(makerspace=maker, title="Event", starts_at=start,
                                 ends_at=start + timedelta(hours=1), registration_audience="accounts", status="draft")
    room = BookableSpace.objects.create(makerspace=maker, name="Room")
    booking = Booking.objects.create(space=room, member=actor, name="Member", email=actor.email,
                                     starts_at=start, ends_at=start + timedelta(hours=1))
    intent = canonical_intent(makerspace_id=maker.pk, event_id=event.pk, booking_id=booking.pk, creator_id=actor.pk)
    row = {"makerspace_id": maker.pk, "event_id": event.pk, "booking_id": booking.pk,
           "creator_id": actor.pk, "generation": uuid4(), "intent_version": 1, "billing_owner": "booking", "revision": 1, "intent": intent}
    actor.account_purged_at = timezone.now(); actor.save(update_fields=["account_purged_at"])
    sticky = decision_import.prepare(row, job=SimpleNamespace(source_makerspace_id=maker.pk),
                                     pk_map=IdentityMap(), references=References(), target=maker)
    assert sticky and row["creator_id"] is None and row["booking_id"] == booking.pk
    decision_import.finish(row, sticky)
    assert row["intent"] == {"version": 1, "unavailable": True}
