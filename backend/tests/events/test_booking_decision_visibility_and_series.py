"""Source regressions for decision visibility, eligibility and retained series history."""
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.bookings.models import BookableSpace, Booking
from apps.events import booking_decision_service as service
from apps.events.models import Event
from apps.events.models_booking_decision import EventBookingDecision
from tests.encryption.conftest import enabled_encryption
from tests.events.orders_helpers import l6_space, make_staff, verified

pytestmark = pytest.mark.django_db(transaction=True)


def sources(slug, *, status="draft", kind="other"):
    maker = l6_space(slug)
    maker.enabled_modules = sorted(set(maker.enabled_modules) | {"bookings"})
    maker.save(update_fields=["enabled_modules"])
    staff, member = make_staff(maker), verified(slug + "-member")
    start = timezone.now() + timedelta(days=2)
    event = Event.objects.create(makerspace=maker, title="Workshop", starts_at=start,
                                 ends_at=start + timedelta(hours=1), status=status)
    room = BookableSpace.objects.create(makerspace=maker, name="Room", kind=kind)
    booking = Booking.objects.create(space=room, member=member, name="Member", email=member.email,
                                     starts_at=start, ends_at=start + timedelta(hours=1))
    kwargs = dict(booking_id=booking.pk, operation_id=uuid4(), expected_generation=None,
                  expected_revision=0, expected_events_epoch=maker.loan_context_generations["events"],
                  expected_bookings_epoch=maker.loan_context_generations["bookings"])
    return maker, staff, event, room, booking, kwargs


def test_hidden_linked_room_is_rejected_before_fee_state(monkeypatch):
    from apps.events import views_booking_decision as view
    maker, staff, event, _room, booking, _kwargs = sources("decision-hidden-room")
    EventBookingDecision.objects.create(makerspace=maker, event=event, booking=booking, creator=staff,
                                        operation_id=uuid4(), intent={})
    monkeypatch.setattr(view, "authorized_event", lambda *_: event)
    monkeypatch.setattr(view, "authorized_booking", lambda *_: (_ for _ in ()).throw(NotFound()))
    checked = []
    monkeypatch.setattr(view, "_fee_state", lambda *_a, **_kw: checked.append(True) or "unresolved")
    with pytest.raises(NotFound):
        view.EventBookingDecisionView().get(SimpleNamespace(user=staff), maker.pk, event.pk)
    assert checked == []


@pytest.mark.parametrize("event_status,room_kind", [
    ("cancelled", "other"), ("completed", "other"), ("draft", "machine"),
])
def test_new_link_refuses_terminal_events_and_machine_time(event_status, room_kind):
    maker, staff, event, _room, _booking, kwargs = sources(
        "decision-ineligible-" + event_status + "-" + room_kind, status=event_status, kind=room_kind)
    with enabled_encryption(), pytest.raises(NotFound):
        service.create_decision(staff, maker, event.pk, **kwargs)
    assert not EventBookingDecision.objects.filter(event=event).exists()


def test_authorized_exact_replay_survives_later_event_cancellation():
    maker, staff, event, _room, _booking, kwargs = sources("decision-retained-replay")
    with enabled_encryption():
        row, replayed = service.create_decision(staff, maker, event.pk, **kwargs)
        assert not replayed
        Event.objects.filter(pk=event.pk).update(status=Event.Status.CANCELLED)
        again, replayed = service.create_decision(staff, maker, event.pk, **kwargs)
    assert replayed and again.pk == row.pk


def test_cancelled_room_stays_linked_without_claiming_a_reservation():
    from apps.bookings.services_transitions import cancel_booking
    from apps.events.views_booking_decision import EventBookingDecisionView

    maker, staff, event, _room, booking, kwargs = sources("decision-room-cancelled")
    view = EventBookingDecisionView()
    request = SimpleNamespace(user=staff)
    with enabled_encryption():
        row, _ = service.create_decision(staff, maker, event.pk, **kwargs)
        before = view.get(request, maker.pk, event.pk).data
        assert before["reservation_state"] in ("pending", "confirmed")
        cancel_booking(booking, actor=staff)
        after = view.get(request, maker.pk, event.pk).data

    assert after["reservation_state"] == "unavailable"
    assert after["state"] == "linked"
    assert after["booking_id"] == booking.pk
    assert after["billing_owner"] == "booking"
    assert after["generation"] == row.generation


def test_recurrence_edit_retains_linked_draft_as_cancelled_history():
    from apps.events import services_series
    from tests.events.test_event_series import create_daily_series, make_manager, make_space

    maker = make_space("decision-series-history")
    actor = make_manager(maker, "decision-series-manager")
    series, occurrences = create_daily_series(maker, actor)
    event = occurrences[0]
    row = EventBookingDecision.objects.create(makerspace=maker, event=event, creator=actor,
                                               operation_id=uuid4(), intent={})
    with enabled_encryption():
        _series, _created, removed = services_series.update_series(series, actor=actor,
                                                                  recurrence_rule="FREQ=WEEKLY")
    event.refresh_from_db()
    assert event.status == Event.Status.CANCELLED and not event.is_public
    assert event.pk not in removed and EventBookingDecision.objects.filter(pk=row.pk, event=event).exists()
