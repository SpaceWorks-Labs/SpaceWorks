"""MI-43 / machines D1: machine time is booked through bookings, and the gate is enforced."""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework import serializers

from apps.bookings.models import BookableSpace, Booking
from apps.bookings.services_spaces import create_space
from apps.machines import booking_gate, role_scope
from apps.machines.models import MachineType
from apps.machines.service_workflow import start
from tests.machines.eta_helpers import approved, enable, owner, world

pytestmark = pytest.mark.django_db


def bookable(w, machine, *, on=True):
    from apps.audit import services as audit
    enable(w.space, "bookings")
    if on:
        w.space.enabled_features = sorted(set(w.space.enabled_features or []) | {"machines.time_booking"})
        w.space.save(update_fields=["enabled_features"])
    return create_space(makerspace=w.space, actor=w.staff, name=f"{machine.name} time", kind="machine",
                        description="", capacity=1, location="", is_public=True, audit_service=audit,
                        machine=machine.pk)


def booking(space, member, *, minutes_ago=10, minutes_left=50):
    now = timezone.now()
    return Booking.objects.create(space=space, member=member, name="Booker", email="b@example.com", phone="1234567890",
                                  starts_at=now - timedelta(minutes=minutes_ago),
                                  ends_at=now + timedelta(minutes=minutes_left))


def test_a_machine_resource_needs_the_switch_and_takes_the_machine_type():
    w = world("book-resource")
    with pytest.raises(Exception):
        bookable(w, w.machines[0], on=False)
    space = bookable(w, w.machines[0])
    assert space.machine_id == w.machines[0].pk and space.machine_type_id == w.kind.pk
    with pytest.raises(serializers.ValidationError):
        bookable(w, w.machines[0])  # one live resource per machine


def test_session_purpose_requires_a_live_booking_when_the_type_requires_one():
    w = world("book-session")
    MachineType.objects.filter(pk=w.kind.pk).update(capability_config={"metering_unit": "minutes",
                                                                       "requires_booking": True})
    w.machines[0].refresh_from_db()
    space = bookable(w, w.machines[0])
    member = owner("book-session-m")
    with pytest.raises(booking_gate.MachineBookingRefused) as refused:
        booking_gate.check(w.machines[0], member, purpose="session")
    assert refused.value.code == "booking_required"
    booking(space, member)
    assert booking_gate.check(w.machines[0], member, purpose="session") is None


def test_service_start_is_refused_while_someone_else_holds_the_machine():
    w = world("book-service")
    space = bookable(w, w.machines[0])
    row = approved(w, 10, created=-5, member=owner("book-service-m"))
    booking(space, owner("book-service-other"))
    with pytest.raises(booking_gate.MachineBookingRefused) as refused:
        start(row, w.staff, role_scope.EXEMPT, machine_id=w.machines[0].pk)
    assert refused.value.code == "machine_booked"
    assert start(row, w.staff, role_scope.EXEMPT, machine_id=w.machines[1].pk).status == "in_progress"


def test_switch_off_enforces_nothing():
    w = world("book-off")
    space = bookable(w, w.machines[0])
    booking(space, owner("book-off-other"))
    w.space.enabled_features = [key for key in w.space.enabled_features if key != "machines.time_booking"]
    w.space.save(update_fields=["enabled_features"])
    assert booking_gate.live_bookings(w.machines[0]) is None
    assert BookableSpace.objects.filter(machine=w.machines[0]).exists()  # data kept
