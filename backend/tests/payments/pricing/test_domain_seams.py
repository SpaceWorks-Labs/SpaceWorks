"""Lane L15 seams: hourly bookings, machine time+material, the events member-discount hook."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.events import services as event_services
from apps.events.models import EventRegistration
from apps.payments.models import Payment, PriceDiscount
from tests.payments.pricing.helpers import D, member, pricing_space, rate
from tests.payments.test_track3_booking_event_charging import bookable, published_event
from tests.return_helpers import make_member

pytestmark = pytest.mark.django_db


def install(space, *modules):
    from apps.makerspaces.module_install import install_module
    for module in modules:
        install_module(space, module)
    space.refresh_from_db()
    features = set(space.enabled_features) | {"charges.bookings", "charges.events", "charges.machines"}
    space.enabled_features = sorted(features)
    space.save(update_fields=["enabled_features", "updated_at"])


def test_hourly_booking_charges_per_booking_plus_rounded_hours_capped_per_day():
    from apps.bookings import services_bookings

    space, _ = pricing_space("seam-booking")
    install(space, "bookings")
    room = bookable(space, amount="5.00")
    rate(space, "bookings", per_hour=("4.00", {"billing_increment": 30, "cap": D("20.00")}))
    booker = member(space)
    starts = timezone.now() + timedelta(hours=2)
    booking = services_bookings.create_booking(room, starts_at=starts, ends_at=starts + timedelta(minutes=70),
                                               member=booker, actor=None)
    payment = Payment.objects.get(subject_type="booking", subject_id=booking.pk)
    assert payment.amount == D("5.00") + D("6.00")  # 70 min -> 90 min billed at 4.00/h
    assert {line["component"] for line in payment.pricing_snapshot["lines"]} == {"per_booking", "per_hour"}


def test_free_room_raises_nothing():
    from apps.bookings import services_bookings

    space, _ = pricing_space("seam-free-room")
    install(space, "bookings")
    room = bookable(space, amount="0")
    starts = timezone.now() + timedelta(hours=2)
    booking = services_bookings.create_booking(room, starts_at=starts, ends_at=starts + timedelta(hours=1),
                                               member=member(space), actor=None)
    assert not Payment.objects.filter(subject_type="booking", subject_id=booking.pk).exists()


def test_event_member_discount_applies_before_the_registration_quote():
    space, manager = pricing_space("seam-event", "charges.discounts")
    install(space, "events")
    staff = make_member("seam-event-staff", space)
    PriceDiscount.objects.create(makerspace=space, name="Members", audience="all_members", percent_bps=5000,
                                 created_by=manager)
    event = published_event(space, staff, amount="8.00")
    attendee = member(space)
    attendee.phone = "+919999999998"
    attendee.save(update_fields=["phone"])
    registration = event_services.register(event, member=attendee, actor=None)
    assert registration.status == EventRegistration.Status.REGISTERED
    assert (registration.quoted_amount, registration.discount_amount) == (D("4.00"), D("4.00"))
    payment = Payment.objects.get(subject_type="event_registration", subject_id=registration.pk)
    assert payment.amount == D("4.00")
    line = payment.pricing_snapshot["lines"][0]
    assert (line["gross"], line["discount"], line["net"]) == ("8.00", "4.00", "4.00")


def test_machine_completion_charges_time_and_material_through_the_kernel():
    from apps.machines.models import Machine, MachineType, MachineServiceRequest
    from apps.machines.service_payments import create_for_completed_request

    space, _ = pricing_space("seam-machine")
    install(space, "machines", "machine_service")
    machine_type = MachineType.objects.create(makerspace=space, name="Printer", slug="printer-seam")
    machine = Machine.objects.create(makerspace=space, machine_type=machine_type, name="P1")
    rate(space, "machines", time="6.00", material="0.05")
    staff = make_member("seam-machine-staff", space)
    requester = member(space)
    from apps.machines.models import ServiceQueue
    queue = ServiceQueue.objects.create(makerspace=space, machine_type=machine_type, name="Queue")
    job = MachineServiceRequest.objects.create(queue=queue, makerspace=space, requester=requester, member=requester,
                                               title="Bracket", assigned_machine=machine, actual_minutes=30,
                                               actual_consumed_grams=D("40"))
    payment = create_for_completed_request(job, staff)
    assert payment.amount == D("5.00")  # 3.00 time + 2.00 material
