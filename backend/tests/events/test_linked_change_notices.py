"""Decision 216 (P1-1/P2-4): an event move or cancellation is told to its linked booking and loans.

The booking and the loan are never changed; each notice is sent once per event version, reaches
only the right people, carries nobody else's details and is silent while a module is off.
"""
from datetime import timedelta

import pytest

from apps.bookings.models import Booking
from apps.events import services
from apps.events.models import Event
from apps.events.models_loan_context import EventLoanContext
from apps.integrations.models_contract import NotificationEnvelope
from tests.encryption.conftest import enabled_encryption
from tests.events.test_booking_decision_replacement import linked
from tests.module_helpers import disable_module
from tests.test_request_workflow import make_hardware_request, make_product

pytestmark = pytest.mark.django_db(transaction=True)


def notices(feature, **filters):
    return list(NotificationEnvelope.objects.filter(feature=feature, event="linked_event_changed", **filters)
                .order_by("pk"))


def move(event, staff, hours=1):
    with enabled_encryption():
        return services.update_event(event, actor=staff, starts_at=event.starts_at + timedelta(hours=hours),
                                     ends_at=event.ends_at + timedelta(hours=hours))


def with_loan(maker, event):
    # Lending modules read as on only while the space's `loans.enabled` capability is on.
    maker.enabled_modules = sorted(set(maker.enabled_modules) | {"request_workflow"})
    maker.enabled_features = sorted(set(maker.enabled_features or []) | {"loans.enabled"})
    maker.save(update_fields=["enabled_modules", "enabled_features"])
    request = make_hardware_request(maker, make_product(maker))
    EventLoanContext.objects.create(makerspace=maker, request=request, event=event, active=True)
    return request


def test_moving_a_linked_event_tells_the_booker_and_booking_staff_once_and_changes_nothing():
    maker, staff, member, event, _room, booking, _decision, _client = linked("lcn-moved")
    before = Booking.objects.values("starts_at", "ends_at", "status").get(pk=booking.pk)
    event = move(event, staff)
    rows = notices("bookings")
    assert [row.recipient_id for row in rows if row.audience == "requester"] == [member.pk]
    assert staff.pk in {row.recipient_id for row in rows if row.audience == "staff"}
    assert {row.source_id for row in rows} == {str(booking.pk)}
    assert Booking.objects.values("starts_at", "ends_at", "status").get(pk=booking.pk) == before
    for row in rows:  # never the event's title (a booking manager may not see it), never a person
        assert "Workshop" not in row.message_body and member.username not in row.message_body
        assert "@" not in row.message_body
    # A repeat of the same revision reserves the same intent; a new revision is a new notice.
    from apps.events.linked_change_notices import notify_linked_booking
    notify_linked_booking(Event.objects.get(pk=event.pk), "moved")
    assert len(notices("bookings")) == len(rows)
    move(Event.objects.get(pk=event.pk), staff)
    assert len(notices("bookings", audience="requester")) == 2


def test_a_details_edit_without_a_time_change_sends_nothing():
    maker, staff, _member, event, *_ = linked("lcn-details")
    with enabled_encryption():
        services.update_event(event, actor=staff, title="Renamed workshop")
    assert notices("bookings") == []


def test_cancelling_a_linked_event_tells_the_booking_and_never_cancels_it():
    maker, staff, member, event, _room, booking, _decision, _client = linked("lcn-cancel")
    Event.objects.filter(pk=event.pk).update(status=Event.Status.PUBLISHED)
    with enabled_encryption():
        services.cancel(Event.objects.get(pk=event.pk), actor=staff)
    assert Booking.objects.get(pk=booking.pk).status == Booking.Status.PENDING
    rows = notices("bookings", audience="requester")
    assert [row.recipient_id for row in rows] == [member.pk] and rows[0].context["change"] == "cancelled"


def test_linked_borrowers_hear_their_due_date_is_unchanged():
    maker, staff, member, event, *_ = linked("lcn-loan")
    request = with_loan(maker, event)
    due_before = request.__class__.objects.values_list("status", flat=True).get(pk=request.pk)
    move(event, staff)
    [row] = notices("hardware_requests")
    assert row.recipient_id == request.requester_id and row.audience == "requester"
    assert "due date has not changed" in row.message_body and member.username not in row.message_body
    assert request.__class__.objects.values_list("status", flat=True).get(pk=request.pk) == due_before


def test_an_inactive_or_returned_loan_hears_nothing():
    maker, staff, _member, event, *_ = linked("lcn-loan-closed")
    request = with_loan(maker, event)
    request.__class__.objects.filter(pk=request.pk).update(status="returned")
    move(event, staff)
    assert notices("hardware_requests") == []


def test_bookings_off_is_silent_for_the_booking_and_loans_still_hear():
    maker, staff, _member, event, *_ = linked("lcn-bookings-off")
    request = with_loan(maker, event)
    disable_module(maker, "bookings")
    move(Event.objects.get(pk=event.pk), staff)
    assert notices("bookings") == []
    assert [row.recipient_id for row in notices("hardware_requests")] == [request.requester_id]


def test_a_notice_written_before_bookings_went_off_is_no_longer_eligible():
    from apps.events.linked_change_notices import booking_notice_eligible
    maker, staff, member, event, *_ = linked("lcn-live-check")
    move(event, staff)
    [row] = notices("bookings", audience="requester")
    assert booking_notice_eligible(row) is True
    disable_module(maker, "bookings")
    row.refresh_from_db()
    assert booking_notice_eligible(row) is False
