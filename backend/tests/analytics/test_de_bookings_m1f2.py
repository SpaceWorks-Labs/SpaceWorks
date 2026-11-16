from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from apps.bookings.models import Booking
from apps.operations import reports
from apps.operations.org_report_aggregate import aggregate_rows
from apps.operations.reports_booking_analytics import build_booking_occupancy
from tests.operations.report_assertions import assert_report_disclosure_safe
from tests.return_helpers import make_member
from .de_helpers_m1f2 import AT, BOUNDS, BOOKING_KEYS, setup, booking

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("grain,expected", [("day", "2026-10-12"), ("week", "2026-10-12"), ("month", "2026-10-01")])
@pytest.mark.parametrize("key", BOOKING_KEYS[:-1])
def test_booking_grains_in_local_calendar(key, grain, expected):
    space, actor = setup(f"de-booking-grain-{key}-{grain}")
    booking(space, actor, created=AT)
    rows = reports.report_data(key, space.pk, actor=actor, grain=grain)["typed_rows"]
    assert rows
    assert {r["period"].date().isoformat() for r in rows} == {expected}
    assert_report_disclosure_safe(rows)


def test_outcomes_bucket_starts_and_clip_cross_period_hours():
    space, actor = setup("de-outcomes")
    first = booking(space, actor, start=AT.replace(hour=23), end=AT.replace(hour=23) + timedelta(hours=2))
    Booking.objects.create(space=first.space, name="No show", email="ns@example.com", phone="1", status="no_show",
                           starts_at=AT + timedelta(days=1), ends_at=AT + timedelta(days=1, hours=1))
    Booking.objects.create(space=first.space, name="Cancelled", email="c@example.com", phone="1", status="cancelled",
                           starts_at=AT + timedelta(days=1, hours=2), ends_at=AT + timedelta(days=1, hours=3))
    rows = reports.report_data("booking-utilization", space.pk, date_range=BOUNDS)["typed_rows"]
    assert len(rows) == 2
    assert rows[0]["completed"] == 1 and rows[0]["completed_hours"] == "1.00"
    assert rows[1]["completed"] == 0 and rows[1]["completed_hours"] == "1.00"
    assert rows[1]["no_show"] == rows[1]["cancelled"] == 1
    assert rows[1]["no_show_rate_percent"] == 100.0
    assert rows[1]["cancellation_rate_percent"] == 50.0


def test_reserved_occupancy_merges_overlaps_and_keeps_empty_hours():
    space, actor = setup("de-occupancy")
    first = booking(space, actor, start=AT, end=AT + timedelta(hours=2))
    Booking.objects.create(space=first.space, name="Overlap", email="overlap@example.com", phone="1", status="confirmed",
                           starts_at=AT + timedelta(hours=1), ends_at=AT + timedelta(hours=3))
    rows = build_booking_occupancy(space.pk, date_range=BOUNDS).records
    assert sum(r["occupied_hours"] for r in rows) == Decimal(3)
    assert sum(r["window_hours"] for r in rows) == Decimal(48)
    assert len(rows) == 48
    assert all(0 <= row["occupancy_percent"] <= 100 for row in rows)


@pytest.mark.parametrize("day,expected", [(datetime(2026, 3, 8, 5, tzinfo=timezone.utc), 23),
                                         (datetime(2026, 11, 1, 4, tzinfo=timezone.utc), 25)])
def test_occupancy_elapsed_hours_at_dst_boundaries(day, expected):
    from zoneinfo import ZoneInfo
    space, actor = setup(f"de-dst-{expected}")
    space.timezone = "America/New_York"
    space.save(update_fields=["timezone"])
    start = day.astimezone(ZoneInfo(space.timezone))
    end = start + timedelta(days=1)
    booking(space, actor, start=start, end=end)
    rows = build_booking_occupancy(space.pk, date_range=(start, end)).records
    assert sum(r["occupied_hours"] for r in rows) == Decimal(expected)
    assert sum(r["window_hours"] for r in rows) == Decimal(expected)


def test_lead_time_includes_after_start_as_a_distinct_bucket():
    space, actor = setup("de-lead-buckets")
    booking(space, actor, created=AT + timedelta(minutes=1))
    booking(space, actor, created=AT - timedelta(hours=24))
    rows = reports.report_data("booking-lead-time", space.pk)["typed_rows"]
    assert {row["lead_time_bucket"] for row in rows} == {"After start", "1–3 days"}
    assert sum(row["booking_count"] for row in rows) == 2


def test_member_ranking_other_includes_all_tail_rows_and_ignores_unattributed():
    space, actor = setup("de-ranking-top")
    for index in range(12):
        member = make_member(f"de-booker-{index}", space)
        booking(space, member)
    unattributed = booking(space, actor)
    Booking.objects.filter(pk=unattributed.pk).update(member=None)
    rows = reports.report_data("booking-top-members", space.pk, actor=actor)["typed_rows"]
    assert len(rows) == 11 and rows[-1]["member"] == "Other"
    assert rows[-1]["booking_count"] == 2
    assert sum(r["booking_count"] for r in rows) == 12


def test_organization_utilization_weights_denominators_and_preserves_periods():
    def row(period, reserved, window, completed, no_show, cancelled):
        return dict(period=period, reserved_hours=Decimal(reserved), window_hours=Decimal(window),
                    completed=completed, no_show=no_show, cancelled=cancelled,
                    terminal_reservations=completed + no_show, reservations=completed + no_show + cancelled)
    source = [(1, [row("2026-10-12", "1", "1", 0, 1, 0)]),
              (2, [row("2026-10-12", "0", "9", 9, 0, 1), row("2026-10-13", "1", "2", 1, 0, 0)])]
    rows = aggregate_rows("booking-utilization", source, limit=10)
    assert rows[0]["reservation_utilization_percent"] == 10.0
    assert rows[0]["no_show_rate_percent"] == 10.0
    assert rows[0]["cancellation_rate_percent"] == 9.09
    assert rows[1]["reservation_utilization_percent"] == 50.0
    assert_report_disclosure_safe(rows)
