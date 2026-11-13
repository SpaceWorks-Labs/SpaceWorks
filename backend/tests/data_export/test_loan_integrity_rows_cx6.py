"""Admission rejects malformed associations using actual stored rows."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.bookings.models_loan_context import BookingLoanContext
from apps.data_export.loan_context_integrity import validate_loan_context_import
from apps.events.models import Event, EventRegistration
from apps.events.models_loan_context import EventLoanContext
from apps.hardware_requests.models import HardwareRequest
from apps.makerspaces.models import Makerspace
from tests.accounts.ua1_helpers import person
from tests.bookings.admin_api_helpers import booking, space as bookable_space

pytestmark = pytest.mark.django_db
EVENT_ERROR = "Imported event loan context failed tenant or borrower validation."
BOOKING_ERROR = "Imported booking loan context failed tenant validation."


@pytest.fixture
def rows():
    home = Makerspace.objects.create(name="Integrity home", slug="cx6-integrity-home")
    away = Makerspace.objects.create(name="Integrity away", slug="cx6-integrity-away")
    borrower = person("cx6-integrity-borrower")
    loan = HardwareRequest.objects.create(makerspace=home, requester=borrower, requester_username=borrower.username)
    start = timezone.now() + timedelta(days=1)
    event = Event.objects.create(makerspace=home, title="Local", starts_at=start, ends_at=start + timedelta(hours=1))
    return home, away, borrower, loan, event


@pytest.mark.parametrize("bad", ["request_tenant", "event_tenant", "registration_event", "registration_borrower"])
def test_each_malformed_event_relationship_is_refused(rows, bad):
    home, away, borrower, loan, event = rows
    other_event = Event.objects.create(makerspace=away if bad == "event_tenant" else home,
        title="Other", starts_at=event.starts_at, ends_at=event.ends_at)
    if bad == "request_tenant":
        loan = HardwareRequest.objects.create(makerspace=away, requester=borrower, requester_username=borrower.username)
    linked_event = other_event if bad == "event_tenant" else event
    registration = EventRegistration.objects.create(
        event=other_event if bad == "registration_event" else linked_event,
        member=person("cx6-integrity-other") if bad == "registration_borrower" else borrower,
        name="Maker", email="maker@example.test", phone="")
    row = EventLoanContext.objects.create(makerspace=home, request=loan, event=linked_event,
                                           participant_registration=registration, active=True)
    with pytest.raises(ValueError) as error:
        validate_loan_context_import(home.pk)
    assert str(error.value) == EVENT_ERROR
    row.refresh_from_db()
    assert (row.active, row.revision) == (True, 1)
    # An invalid association in HOME cannot break admission of AWAY's independent closure.
    assert validate_loan_context_import(away.pk) is None


@pytest.mark.parametrize("bad", ["request_tenant", "booking_tenant"])
def test_each_malformed_booking_relationship_is_refused(rows, bad):
    home, away, borrower, loan, _ = rows
    if bad == "request_tenant":
        loan = HardwareRequest.objects.create(makerspace=away, requester=borrower, requester_username=borrower.username)
    reserved = booking(bookable_space(away if bad == "booking_tenant" else home), member=borrower)
    row = BookingLoanContext.objects.create(makerspace=home, request=loan, booking=reserved, active=True)
    with pytest.raises(ValueError) as error:
        validate_loan_context_import(home.pk)
    assert str(error.value) == BOOKING_ERROR
    row.refresh_from_db()
    assert (row.active, row.revision) == (True, 1)
    assert validate_loan_context_import(away.pk) is None


def test_valid_repeated_borrower_and_detached_contexts_are_admitted(rows):
    home, _, borrower, loan, event = rows
    registration = EventRegistration.objects.create(event=event, member=borrower, name="Maker", email="maker@example.test", phone="")
    EventLoanContext.objects.create(makerspace=home, request=loan, event=event, participant_registration=registration, active=True)
    for index in range(2):
        another = HardwareRequest.objects.create(makerspace=home, requester=borrower, requester_username=borrower.username)
        EventLoanContext.objects.create(makerspace=home, request=another,
            event=event if index == 0 else None, participant_registration=registration if index == 0 else None,
            active=index == 0)
    assert validate_loan_context_import(home.pk) is None
    assert EventLoanContext.objects.filter(makerspace=home).count() == 3
