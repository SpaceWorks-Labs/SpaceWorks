"""Source tests for 3A replay and transactional lock failures; unrun."""
from datetime import timedelta
from uuid import uuid4

import pytest
from django.db import DatabaseError
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.bookings.models import BookableSpace, Booking
from apps.events import booking_decision_service as service
from apps.events.models import Event
from apps.events.models_booking_decision import EventBookingDecision
from tests.encryption.conftest import enabled_encryption
from tests.events.orders_helpers import l6_space, make_staff, verified

pytestmark = pytest.mark.django_db(transaction=True)


def test_authorized_exact_replay_precedes_stale_epochs_and_reuses_decision():
    maker = l6_space("booking-decision-replay")
    maker.enabled_modules = sorted(set(maker.enabled_modules) | {"bookings"})
    maker.save(update_fields=["enabled_modules"])
    staff, member = make_staff(maker), verified("booking-decision-borrower")
    start = timezone.now() + timedelta(days=2)
    event = Event.objects.create(makerspace=maker, title="Workshop", starts_at=start,
                                 ends_at=start + timedelta(hours=1), registration_audience="accounts",
                                 is_public=True, status="draft")
    room = BookableSpace.objects.create(makerspace=maker, name="Room")
    booking = Booking.objects.create(space=room, member=member, name="Borrower", email=member.email,
                                     starts_at=start, ends_at=start + timedelta(hours=1))
    token = uuid4()
    kwargs = dict(booking_id=booking.pk, operation_id=token, expected_generation=None, expected_revision=0,
                  expected_events_epoch=maker.loan_context_generations["events"],
                  expected_bookings_epoch=maker.loan_context_generations["bookings"])
    with enabled_encryption():
        row, replayed = service.create_decision(staff, maker, event.pk, **kwargs)
        assert replayed is False
        again, replayed = service.create_decision(staff, maker, event.pk,
            **{**kwargs, "expected_events_epoch": uuid4(), "expected_bookings_epoch": uuid4()})
    assert replayed is True and again.pk == row.pk
    assert EventBookingDecision.objects.filter(makerspace=maker).count() == 1


@pytest.mark.parametrize("sqlstate", ["55P03", "40P01"])
def test_lock_failure_maps_to_conflict_after_boundary_unwinds(monkeypatch, sqlstate):
    class Cause(Exception):
        pass
    cause = Cause(); cause.sqlstate = sqlstate
    def refuse(*_args, **_kwargs):
        raise DatabaseError("database lock") from cause
    monkeypatch.setattr(service, "_create_once", refuse)
    with pytest.raises(service.DecisionConflict) as exc:
        service.create_decision(None, None, 1, booking_id=1, operation_id=uuid4(), expected_generation=None,
                                expected_revision=0, expected_events_epoch=uuid4(), expected_bookings_epoch=uuid4())
    assert exc.value.detail["code"] == "lock_busy"


def test_purged_original_creator_cannot_authorize_replay():
    from types import SimpleNamespace
    creator = verified("decision-purged-creator")
    decision = SimpleNamespace(creator_id=creator.pk, creator=creator)
    service._auth_original(creator, decision)
    creator.account_purged_at = timezone.now()
    creator.save(update_fields=["account_purged_at"])
    with pytest.raises(NotFound):
        service._auth_original(creator, decision)
