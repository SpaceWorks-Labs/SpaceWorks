"""#159: a booking awaiting approval is charged the price quoted when it was requested."""

from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.bookings import services_bookings
from apps.bookings.models import Booking
from apps.payments.models import Payment
from tests.payments.pricing.helpers import D, member, pricing_space, rate
from tests.payments.pricing.test_domain_seams import install
from tests.payments.test_track3_booking_event_charging import bookable
from tests.return_helpers import make_member

pytestmark = pytest.mark.django_db


@pytest.fixture
def setup():
    space, _ = pricing_space("req-price")
    install(space, "bookings")
    manager = make_member("req-price-staff", space)
    return space, manager, member(space)


def book(room, booker, minutes=60):
    starts = timezone.now() + timedelta(days=1)
    return services_bookings.create_booking(room, starts_at=starts, ends_at=starts + timedelta(minutes=minutes),
                                            member=booker, actor=booker)


def charge(booking):
    return Payment.objects.filter(subject_type="booking", subject_id=booking.pk).first()


def test_price_change_between_request_and_approval_charges_the_requested_price(setup):
    space, manager, booker = setup
    room = bookable(space, approval_mode="approve", amount="5.00")
    rate(space, "bookings", per_hour="4.00")
    pending = book(room, booker)
    assert pending.status == Booking.Status.PENDING and charge(pending) is None
    assert D(pending.pricing_snapshot["total"]) == D("9.00")
    room.payment_amount = D("50.00")
    room.save(update_fields=["payment_amount"])
    rate(space, "bookings", per_hour="40.00")
    services_bookings.approve_booking(pending, actor=manager)
    payment = charge(pending)
    assert payment.amount == D("9.00") and payment.pricing_snapshot["frozen_at"] == "request"
    assert not AuditLog.objects.filter(action="booking.price_quoted_at_approval").exists()


def test_a_legacy_request_without_a_frozen_price_falls_back_and_is_audited(setup):
    space, manager, booker = setup
    room = bookable(space, approval_mode="approve", amount="5.00")
    pending = book(room, booker)
    with connection.cursor() as cursor:  # a row from before #159: no frozen quote
        cursor.execute("SET session_replication_role = 'replica'")
        cursor.execute("UPDATE bookings_booking SET pricing_snapshot = '{}'::jsonb WHERE id = %s", [pending.pk])
        cursor.execute("SET session_replication_role = 'origin'")
    room.payment_amount = D("7.00")
    room.save(update_fields=["payment_amount"])
    services_bookings.approve_booking(Booking.objects.get(pk=pending.pk), actor=manager)
    assert charge(pending).amount == D("7.00")
    assert AuditLog.objects.filter(action="booking.price_quoted_at_approval", meta__booking_id=pending.pk).exists()


def test_an_instant_confirmation_is_unchanged(setup):
    space, _manager, booker = setup
    room = bookable(space, amount="5.00")
    rate(space, "bookings", per_hour="4.00")
    confirmed = book(room, booker, minutes=30)
    assert confirmed.status == Booking.Status.CONFIRMED and confirmed.pricing_snapshot == {}
    assert charge(confirmed).amount == D("7.00")


def test_the_requested_price_is_frozen_in_the_model_and_the_database(setup):
    space, _manager, booker = setup
    pending = book(bookable(space, approval_mode="approve", amount="5.00"), booker)
    pending.pricing_snapshot = {"total": "1.00"}
    with pytest.raises(ValidationError):
        pending.save()
    with pytest.raises(Exception):
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("UPDATE bookings_booking SET pricing_snapshot = '{}'::jsonb WHERE id = %s", [pending.pk])


def test_staff_see_the_requested_price(setup):
    from tests.payments.pricing.helpers import client

    space, manager, booker = setup
    room = bookable(space, approval_mode="approve", amount="5.00")
    pending = book(room, booker)
    from apps.bookings.serializers_reservation import BookingAdminSerializer
    data = BookingAdminSerializer(Booking.objects.get(pk=pending.pk)).data
    assert data["requested_price"] == {"total": "5.00", "currency": "usd", "discount_total": "0"}
    assert client(manager)  # the staff surfaces render this field next to Approve
