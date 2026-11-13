"""Flow audit conditions 3 and 4 across modules: last unit across loan+event, slot races, DST and boundaries.

Real PostgreSQL row locks, two threads released by one barrier; the loser must get a typed refusal and the shared
quantity/slot must never go below zero or be double-booked.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone as dt_tz
from threading import Barrier
from zoneinfo import ZoneInfo

import pytest
from django.db import close_old_connections, connection
from django.utils import timezone

from apps.bookings import services_bookings
from apps.bookings.exceptions import BookingConflict
from apps.bookings.models import Booking
from apps.events.models import Event
from apps.events.models_loan_context import EventLoanContext
from apps.hardware_requests import workflow
from apps.hardware_requests.models import HardwareRequest
from apps.inventory.availability import InsufficientStock
from apps.separability import equipment_context_bridge as bridge
from tests.encryption.conftest import enabled_encryption
from tests.events.orders_helpers import l6_space, make_staff
from tests.inventory.test_reservations import member, space_with, stock, submit
from tests.kit_helpers import kit_setup
from tests.payments.test_track3_booking_event_charging import bookable, member_with_phone
from tests.return_helpers import make_member, make_product

pytestmark = pytest.mark.django_db(transaction=True)


def _race(*jobs):
    barrier = Barrier(len(jobs))

    def run(job):
        close_old_connections()
        try:
            barrier.wait(timeout=15)
            try:
                return ("ok", job())
            except Exception as exc:  # the loser's typed refusal is the thing under test
                return ("err", exc)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        return [f.result(timeout=60) for f in [pool.submit(run, j) for j in jobs]]


def _loans_on(space, *modules):
    space.enabled_modules = sorted(set(space.enabled_modules) | {"events", "request_workflow", *modules})
    space.enabled_features = sorted(set(space.enabled_features or []) | {"loans.enabled"})
    space.save(update_fields=["enabled_modules", "enabled_features"])


def test_two_staff_accepting_the_last_unit_for_an_event_loan_and_an_ordinary_loan_reserve_it_once():
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    space = space_with("fa-race-unit")
    _loans_on(space)
    staff_a, staff_b = make_member("fa-race-a", space), make_member("fa-race-b", space)
    product = make_product(space, available_quantity=1, total_quantity=1)
    event = Event.objects.create(makerspace=space, title="Hack night", starts_at=timezone.now() + timedelta(days=2),
                                 ends_at=timezone.now() + timedelta(days=2, hours=3), status=Event.Status.PUBLISHED)
    for_event = submit(space, member(space, "fa-race-r1"), product)
    ordinary = submit(space, member(space, "fa-race-r2"), product)
    EventLoanContext.objects.create(makerspace=space, request=for_event, event=event, active=True)
    results = _race(lambda: workflow.accept_request(staff_a, for_event),
                    lambda: workflow.accept_request(staff_b, ordinary))
    assert sorted(kind for kind, _ in results) == ["err", "ok"]
    loser = next(value for kind, value in results if kind == "err")
    assert isinstance(loser, InsufficientStock)
    assert stock(product) == (0, 1)  # never negative, exactly one reservation
    statuses = list(HardwareRequest.objects.filter(pk__in=[for_event.pk, ordinary.pk]).values_list("status", flat=True))
    assert statuses.count("accepted") == 1
    assert EventLoanContext.objects.filter(request=for_event, active=True).count() == 1  # the link survives a refusal


def test_two_actors_booking_the_same_free_slot_for_an_event_and_for_themselves_leave_one_booking():
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    maker = l6_space("fa-race-slot")
    maker.enabled_modules = sorted(set(maker.enabled_modules) | {"bookings"})
    maker.save(update_fields=["enabled_modules"])
    organiser, other = member_with_phone("fa-slot-org", maker), member_with_phone("fa-slot-other", maker)
    staff = make_staff(maker)
    room = bookable(maker)  # instant confirmation: the first confirmed booking owns the slot
    start = timezone.now() + timedelta(days=2)
    end = start + timedelta(hours=1)

    def book(person, actor):
        def go():
            with enabled_encryption():
                return services_bookings.create_booking(room, starts_at=start, ends_at=end, member=person, actor=actor)
        return go

    results = _race(book(organiser, staff), book(other, other))
    assert sorted(kind for kind, _ in results) == ["err", "ok"]
    assert isinstance(next(v for k, v in results if k == "err"), BookingConflict)
    live = Booking.objects.filter(space=room, starts_at=start).exclude(status__in=["cancelled", "rejected"])
    assert live.count() == 1


def _event_loan(slug, ends, **event_fields):
    data = kit_setup(slug, product_kit=False)
    _loans_on(data.space)
    event = Event.objects.create(makerspace=data.space, title="Timed", starts_at=ends - timedelta(hours=3),
                                 ends_at=ends, status=Event.Status.PUBLISHED, **event_fields)
    EventLoanContext.objects.create(makerspace=data.space, request=data.request, event=event, active=True)
    return data, event


def test_an_event_loan_due_back_across_a_spring_forward_is_exactly_the_stated_hours_in_the_spaces_zone():
    zone = ZoneInfo("America/New_York")
    ends = datetime(2026, 3, 8, 1, 30, tzinfo=zone)  # 30 minutes before the 02:00 spring-forward jump
    data, _event = _event_loan("fa-dst-spring", ends, equipment_return_hours=24)
    due = bridge.event_return_due(data.request, ends - timedelta(days=1))
    assert due - ends == timedelta(hours=24)  # real hours: 24h elapsed, not "same clock time tomorrow"
    assert due.astimezone(zone) == datetime(2026, 3, 9, 2, 30, tzinfo=zone)  # 01:30 EST + 24h is 02:30 EDT
    assert due.astimezone(dt_tz.utc) == datetime(2026, 3, 9, 6, 30, tzinfo=dt_tz.utc)


def test_an_event_loan_due_back_across_a_fall_back_is_exactly_the_stated_hours():
    zone = ZoneInfo("America/New_York")
    ends = datetime(2026, 11, 1, 0, 30, tzinfo=zone)  # the evening before the clocks go back
    data, _event = _event_loan("fa-dst-fall", ends, equipment_return_hours=24)
    due = bridge.event_return_due(data.request, ends - timedelta(days=1))
    assert due - ends == timedelta(hours=24)
    assert due.astimezone(zone) == datetime(2026, 11, 1, 23, 30, tzinfo=zone)  # 24 real hours span the extra hour


def test_the_due_time_exactly_at_issue_is_not_used_and_one_microsecond_earlier_is():
    ends = timezone.now() + timedelta(days=1)
    data, _event = _event_loan("fa-boundary", ends)
    assert bridge.event_return_due(data.request, ends) is None  # due == issued_at: not strictly in the future
    assert bridge.event_return_due(data.request, ends + timedelta(microseconds=1)) is None
    assert bridge.event_return_due(data.request, ends - timedelta(microseconds=1)) == ends
