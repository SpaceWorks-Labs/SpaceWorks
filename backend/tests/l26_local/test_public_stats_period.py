"""L26 (#170): the fixed period, on the space's own wall clock; "fy" uses L4's fy_bounds."""

from datetime import datetime, timezone as dt_timezone
from zoneinfo import ZoneInfo

import pytest

from apps.inventory.public_stats_period import period_window
from apps.makerspaces.models import Makerspace

pytestmark = pytest.mark.django_db
NOW = datetime(2026, 11, 2, 12, 0, tzinfo=dt_timezone.utc)


def space(**fields):
    return Makerspace.objects.create(name="p", slug=f"l26-period-{len(fields)}-{fields.get('timezone', 'x')[:3].lower()}",
                                     **fields)


def local(makerspace, instant):
    return instant.astimezone(ZoneInfo(makerspace.timezone)).replace(tzinfo=None)


def test_month_year_and_all():
    makerspace = space(timezone="Asia/Kolkata")
    month = period_window(makerspace, "month", NOW)
    assert (local(makerspace, month.start), local(makerspace, month.end)) == (
        datetime(2026, 11, 1), datetime(2026, 12, 1))
    assert month.label == "November 2026"
    year = period_window(makerspace, "year", NOW)
    assert (local(makerspace, year.start), local(makerspace, year.end)) == (datetime(2026, 1, 1), datetime(2027, 1, 1))
    every = period_window(makerspace, "all", NOW)
    assert every.start is None and every.end is None and every.until_now() == (None, NOW)
    assert month.until_now() == (month.start, NOW)


def test_month_rolls_over_december():
    makerspace = space(timezone="UTC")
    month = period_window(makerspace, "month", datetime(2026, 12, 31, 23, 0, tzinfo=dt_timezone.utc))
    assert (month.start.date().isoformat(), month.end.date().isoformat()) == ("2026-12-01", "2027-01-01")


def test_fy_uses_the_space_financial_year():
    makerspace = space(timezone="UTC", financial_year_start_month=4)
    fy = period_window(makerspace, "fy", NOW)
    assert (fy.start.date().isoformat(), fy.end.date().isoformat()) == ("2026-04-01", "2027-04-01")
    assert fy.label == "FY 2026-27"
    january = Makerspace.objects.create(name="j", slug="l26-period-jan", timezone="UTC", financial_year_start_month=1)
    calendar = period_window(january, "fy", NOW)
    assert (calendar.start.date().isoformat(), calendar.label) == ("2026-01-01", "FY 2026")


def test_local_wall_clock_decides_the_month():
    makerspace = space(timezone="Pacific/Auckland")
    # 2026-10-31 20:00 UTC is already 1 November in Auckland.
    month = period_window(makerspace, "month", datetime(2026, 10, 31, 20, 0, tzinfo=dt_timezone.utc))
    assert month.label == "November 2026"
