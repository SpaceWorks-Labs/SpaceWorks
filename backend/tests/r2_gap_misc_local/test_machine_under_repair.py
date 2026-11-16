"""Lane r2-gap-misc, gap 19: a machine under repair refuses new bookings of its time.

Local, untracked (#175): run in the test phase on the combined tree. Mirrors the L16 room-outage
test (tests/maintenance/test_l16_service_state.py): taking a machine out of service lists the
bookings already made to staff (booking authority only), new overlapping bookings are refused with
a typed 409, a booking after the expected-back time still goes through, and back in service the
machine books again.
"""
from datetime import timedelta
from unittest import mock

import pytest
from rest_framework.views import exception_handler

from apps.bookings.exceptions import BookingConflict, MachineUnderRepair
from apps.bookings.models import BookableSpace, Booking
from apps.bookings.services_bookings import create_booking
from apps.machines import booking_gate
from apps.maintenance.repairs import notify, service_state
from tests.machines.certification_helpers import _member
from tests.maintenance.l16_helpers import switch, tomorrow, world
from tests.return_helpers import authenticated_client

pytestmark = pytest.mark.django_db


def machine_world(slug):
    w = world(slug)
    switch(w.space, on=("machines.time_booking",))
    w.time = BookableSpace.objects.create(makerspace=w.space, name="Laser A time", machine=w.machine,
                                          machine_type=w.kind, approval_mode=BookableSpace.ApprovalMode.INSTANT)
    w.member, _ = _member(w.space, f"{slug}-member")
    return w


def post_state(user, w, **body):
    return authenticated_client(user).post(f"/api/v1/admin/makerspaces/{w.space.pk}/service-state", body,
                                           format="json")


def book(w, start, end):
    return create_booking(w.time, member=w.member, actor=w.member, starts_at=start, ends_at=end)


def test_repair_lists_affected_bookings_and_refuses_new_ones_with_a_typed_error():
    w = machine_world("gap19-repair")
    start, end = tomorrow()
    booked = book(w, start, end)
    back = start + timedelta(days=2)
    with mock.patch.object(notify, "_email", return_value=1) as mailed:
        out = post_state(w.manager, w, subject_type="machine", subject_id=w.machine.pk, in_service=False,
                         reason="Tube cracked", expected_back_at=back.isoformat())
    assert out.status_code == 200, out.content
    assert out.json()["state"] == "maintenance"
    assert [row["id"] for row in out.json()["affected_bookings"]] == [booked.pk]
    assert mailed.call_count == 1 and mailed.call_args.kwargs["event"] == "machine_repair"
    with pytest.raises(MachineUnderRepair) as refused:
        book(w, start + timedelta(days=1), end + timedelta(days=1))
    assert isinstance(refused.value, BookingConflict)
    response = exception_handler(refused.value, {})
    assert response.status_code == 409
    assert response.data == {"detail": "This machine is out of service for repair at that time.",
                             "code": "machine_under_repair"}
    after = book(w, back + timedelta(hours=1), back + timedelta(hours=2))  # after it is expected back
    assert after.status == Booking.Status.CONFIRMED


def test_without_an_expected_back_time_every_future_booking_is_refused_until_it_returns():
    w = machine_world("gap19-open")
    service_state.set_state(w.manager, w.space, subject_type="machine", subject=w.machine, in_service=False)
    start, end = tomorrow()
    with pytest.raises(MachineUnderRepair):
        book(w, start + timedelta(days=30), end + timedelta(days=30))
    w.machine.refresh_from_db()
    service_state.set_state(w.manager, w.space, subject_type="machine", subject=w.machine, in_service=True)
    assert book(w, start, end).status == Booking.Status.CONFIRMED


def test_affected_bookings_are_listed_only_to_booking_authority():
    w = machine_world("gap19-scope")
    start, end = tomorrow()
    book(w, start, end)
    from tests.maintenance.l16_helpers import in_house
    in_house(w, coverage=[{"kind": "machine_type", "machine_type": w.kind}])
    out = post_state(w.tech, w, subject_type="machine", subject_id=w.machine.pk, in_service=False)
    assert out.status_code == 200, out.content
    assert out.json()["affected_bookings"] == []  # a technician decides nothing about bookings


def test_a_machine_already_under_repair_does_not_re_mail_its_bookers():
    w = machine_world("gap19-twice")
    start, end = tomorrow()
    book(w, start, end)
    with mock.patch.object(notify, "_email", return_value=1) as mailed:
        first = service_state.set_state(w.manager, w.space, subject_type="machine", subject=w.machine, in_service=False)
        w.machine.refresh_from_db()
        again = service_state.set_state(w.manager, w.space, subject_type="machine", subject=w.machine, in_service=False)
    assert len(first["bookings"]) == 1 and again["bookings"] == []
    assert mailed.call_count == 1


def test_the_gate_is_quiet_for_a_working_machine_and_ignores_rooms():
    w = machine_world("gap19-quiet")
    start, end = tomorrow()
    assert booking_gate.repair_window(w.machine) is None
    booking_gate.refuse_if_under_repair(w.machine, start, end)  # no error
    service_state.set_state(w.manager, w.space, subject_type="machine", subject=w.machine, in_service=False)
    room = create_booking(w.room, member=w.member, actor=w.member, starts_at=start, ends_at=end)
    assert room.status == Booking.Status.CONFIRMED  # a room is never gated by a machine's repair
    assert booking_gate.bookings_in_repair(w.machine) == []



def test_a_weekly_series_reports_the_repair_window_as_a_plain_conflict():
    from apps.bookings.services_recurrence import create_recurring_bookings
    w = machine_world("gap19-series")
    switch(w.space, on=("bookings.recurring",))
    start, end = tomorrow()
    service_state.set_state(w.manager, w.space, subject_type="machine", subject=w.machine, in_service=False,
                            expected_back_at=start + timedelta(days=3))
    rows = create_recurring_bookings(w.time, actor=w.manager, member=w.member, starts_at=start, ends_at=end, count=2)
    assert [row["status"] for row in rows] == ["conflict", Booking.Status.CONFIRMED]
    assert rows[0]["detail"] == "This machine is out of service for repair at that time."
