"""MOD-1 condition 4: loan due instants across DST changes, month and year ends, in the space's own zone."""
from datetime import datetime, timezone as dt_timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from apps.hardware_requests.due_policy import closed_notice, effective_due, effective_pickup_deadline

NY = ZoneInfo("America/New_York")
EVERY_DAY = {day: [{"start": "09:00", "end": "17:00"}] for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
WEEKDAYS = {day: EVERY_DAY[day] for day in ("mon", "tue", "wed", "thu", "fri")}


def space(weekly, tz="America/New_York"):
    return SimpleNamespace(timezone=tz, opening_hours={"weekly": weekly})


def local(*args, tz=NY):
    return datetime(*args, tzinfo=tz)


def test_fall_back_night_rolls_to_the_next_morning_in_standard_time():
    # 2026-10-31 18:00 EDT is closed. Clocks fall back on Sun 2026-11-01, so the reopening
    # 09:00 is EST (UTC-5): 14:00 UTC, plus the one-hour grace = 15:00 UTC.
    rolled = effective_due(space(EVERY_DAY), local(2026, 10, 31, 18, 0))
    assert rolled == datetime(2026, 11, 1, 15, 0, tzinfo=dt_timezone.utc)
    assert rolled.astimezone(NY).hour == 10


def test_spring_forward_night_rolls_to_the_next_morning_in_daylight_time():
    # Sat 2026-03-07 18:00 EST is closed; Sun 03-08 09:00 is EDT (UTC-4): 13:00 UTC, +1h = 14:00 UTC.
    rolled = effective_due(space(EVERY_DAY), local(2026, 3, 7, 18, 0))
    assert rolled == datetime(2026, 3, 8, 14, 0, tzinfo=dt_timezone.utc)
    assert rolled.astimezone(NY).hour == 10


def test_the_closing_instant_on_a_dst_change_day_is_still_returnable_in_local_time():
    # 17:00 local on the fall-back day is 22:00 UTC (EST); it is the closing instant and is kept.
    closing = local(2026, 11, 1, 17, 0)
    assert effective_due(space(EVERY_DAY), closing) == closing
    one_minute_later = local(2026, 11, 1, 17, 1)
    assert effective_due(space(EVERY_DAY), one_minute_later) == datetime(2026, 11, 2, 15, 0, tzinfo=dt_timezone.utc)


def test_month_end_weekend_rolls_into_the_next_month():
    # Sat 2026-01-31 12:00 is closed (weekday-only hours): Monday 2026-02-02 09:00 EST + 1h.
    assert effective_due(space(WEEKDAYS), local(2026, 1, 31, 12, 0)) == local(2026, 2, 2, 10, 0)


def test_year_end_evening_rolls_into_the_new_year():
    # Thu 2026-12-31 18:00 closed; Fri 2027-01-01 09:00 EST + 1h.
    assert effective_due(space(WEEKDAYS), local(2026, 12, 31, 18, 0)) == local(2027, 1, 1, 10, 0)


def test_leap_day_is_a_normal_open_day():
    # 2028-02-29 is a Tuesday: a due inside opening hours is untouched.
    inside = local(2028, 2, 29, 11, 0)
    assert effective_due(space(WEEKDAYS), inside) == inside


def test_the_same_utc_instant_is_open_in_one_space_and_closed_in_another():
    instant = datetime(2026, 11, 16, 14, 30, tzinfo=dt_timezone.utc)  # Monday
    assert effective_due(space(WEEKDAYS, "America/New_York"), instant) == instant  # 09:30 EST open
    assert effective_due(space(WEEKDAYS, "Asia/Tokyo"), instant) != instant  # 23:30 JST closed


def test_pickup_deadline_in_a_closed_dst_night_rolls_to_the_next_session_close_not_its_opening():
    rolled = effective_pickup_deadline(space(EVERY_DAY), local(2026, 10, 31, 18, 0))
    assert rolled == local(2026, 11, 1, 17, 0)  # close of Sunday's session, EST


def test_closed_notice_reports_the_next_opening_as_an_instant_on_the_correct_side_of_the_change():
    notice = closed_notice(space(EVERY_DAY), local(2026, 10, 31, 18, 0))
    assert notice["code"] == "space_closed"
    assert datetime.fromisoformat(notice["next_open_at"]) == datetime(2026, 11, 1, 14, 0, tzinfo=dt_timezone.utc)


@pytest.mark.parametrize("due", [None])
def test_no_due_is_a_no_op(due):
    assert effective_due(space(EVERY_DAY), due) is None
    assert closed_notice(space(EVERY_DAY), due) is None
