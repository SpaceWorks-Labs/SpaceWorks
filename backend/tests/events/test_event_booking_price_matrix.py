"""PostgreSQL regression draft for V5: registration and room debt are independent."""
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.bookings.services_bookings import create_booking
from apps.events import booking_decision_service, services
from apps.events.models import Event
from apps.payments.models import Payment
from tests.encryption.conftest import enabled_encryption
from tests.events.orders_helpers import l6_space, make_staff
from tests.payments.test_track3_booking_event_charging import bookable, member_with_phone

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("registration_amount,room_amount,booking_charges", [
    ("0.00", "0.00", True), ("0.00", "12.50", True),
    ("8.00", "0.00", True), ("8.00", "12.50", True),
    ("8.00", "12.50", False),
])
def test_link_and_publish_keep_registration_and_booking_debts_independent(
        registration_amount, room_amount, booking_charges):
    maker = l6_space("booking-price-matrix")
    maker.enabled_modules = sorted(set(maker.enabled_modules) | {"bookings"})
    features = set(maker.enabled_features) | {"charges.enabled", "charges.events"}
    if booking_charges:
        features.add("charges.bookings")
    else:
        features.discard("charges.bookings")
    maker.enabled_features = sorted(features)
    maker.save(update_fields=["enabled_modules", "enabled_features"])
    staff = make_staff(maker)
    member = member_with_phone("booking-price-member", maker)
    start = timezone.now() + timedelta(days=2)
    event = Event.objects.create(makerspace=maker, title="Workshop", starts_at=start,
        ends_at=start + timedelta(hours=1), registration_audience="accounts", is_public=True,
        status=Event.Status.DRAFT, payment_amount=Decimal(registration_amount))
    room = bookable(maker, amount=room_amount)
    with enabled_encryption():
        booking = create_booking(room, starts_at=start, ends_at=event.ends_at, member=member, actor=member)
        before = list(Payment.objects.filter(makerspace=maker).order_by("pk").values_list(
            "pk", "subject_type", "subject_id", "amount"))
        decision, replayed = booking_decision_service.create_decision(staff, maker, event.pk,
            booking_id=booking.pk, operation_id=uuid4(), expected_generation=None, expected_revision=0,
            expected_events_epoch=maker.loan_context_generations["events"],
            expected_bookings_epoch=maker.loan_context_generations["bookings"])
        assert not replayed and decision.booking_id == booking.pk
        assert list(Payment.objects.filter(makerspace=maker).order_by("pk").values_list(
            "pk", "subject_type", "subject_id", "amount")) == before
        services.publish(event, actor=staff)
        assert list(Payment.objects.filter(makerspace=maker).order_by("pk").values_list(
            "pk", "subject_type", "subject_id", "amount")) == before
        registration = services.register(event, member=member, actor=None)
    booking_rows = Payment.objects.filter(makerspace=maker, subject_type=Payment.SubjectType.BOOKING,
                                          subject_id=booking.pk)
    registration_rows = Payment.objects.filter(makerspace=maker,
        subject_type=Payment.SubjectType.EVENT_REGISTRATION, subject_id=registration.pk)
    assert booking_rows.count() == int(booking_charges and Decimal(room_amount) > 0)
    assert registration_rows.count() == int(Decimal(registration_amount) > 0)
    if booking_rows.exists():
        assert booking_rows.get().amount == Decimal(room_amount)
        assert booking_rows.get().provider == "unclaimed"
    if registration_rows.exists():
        assert registration_rows.get().amount == Decimal(registration_amount)
    assert not Payment.objects.filter(makerspace=maker, subject_type="event_venue_fee").exists()


def test_configured_event_venue_fee_blocks_linking_so_the_room_is_never_charged_twice():
    from apps.events import venue_fees
    from apps.events.models_booking_decision import EventBookingDecision

    maker = l6_space("booking-price-venue-fee")
    maker.enabled_modules = sorted(set(maker.enabled_modules) | {"bookings"})
    maker.enabled_features = sorted(set(maker.enabled_features) | {"charges.enabled", "charges.events",
                                                                    "charges.bookings"})
    maker.save(update_fields=["enabled_modules", "enabled_features"])
    staff = make_staff(maker)
    member = member_with_phone("booking-price-venue-member", maker)
    start = timezone.now() + timedelta(days=2)
    event = Event.objects.create(makerspace=maker, title="Workshop", starts_at=start,
        ends_at=start + timedelta(hours=1), status=Event.Status.DRAFT)
    room = bookable(maker, amount="12.50")
    venue_fees.configure(event, actor=staff, payer=member, mode="custom", basis="flat", amount="10.00")
    with enabled_encryption():
        booking = create_booking(room, starts_at=start, ends_at=event.ends_at, member=member, actor=member)
        with pytest.raises(booking_decision_service.DecisionConflict) as refused:
            booking_decision_service.create_decision(staff, maker, event.pk,
                booking_id=booking.pk, operation_id=uuid4(), expected_generation=None, expected_revision=0,
                expected_events_epoch=maker.loan_context_generations["events"],
                expected_bookings_epoch=maker.loan_context_generations["bookings"])
    assert refused.value.detail["code"] == "venue_fee_unresolved"
    assert not EventBookingDecision.objects.filter(event=event).exists()
    assert not Payment.objects.filter(makerspace=maker, subject_type="event_venue_fee").exists()
