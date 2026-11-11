"""#227 m14: `previous_close`, the mirror of `next_opening`, and the guest due cap that uses it."""
from datetime import datetime, timedelta, timezone as tz
from types import SimpleNamespace

from apps.makerspaces.opening_hours import next_opening, previous_close

_WEEK = {day: [{"start": "09:00", "end": "17:00"}] for day in
         ("monday", "tuesday", "wednesday", "thursday", "friday")}
_SPACE = SimpleNamespace(timezone="UTC", opening_hours={"weekly": _WEEK})


def _at(day, hour, minute=0):
    return datetime(2026, 11, day, hour, minute, tzinfo=tz.utc)  # 2026-11-09 is a Monday


def test_open_instant_and_a_space_without_hours_return_the_instant():
    assert previous_close(_SPACE, _at(9, 12)) == _at(9, 12)
    always = SimpleNamespace(timezone="UTC", opening_hours={})
    assert previous_close(always, _at(9, 3)) == _at(9, 3)


def test_evening_and_early_morning_roll_back_to_the_last_close():
    assert previous_close(_SPACE, _at(9, 20)) == _at(9, 17)
    assert previous_close(_SPACE, _at(10, 6)) == _at(9, 17)


def test_weekend_rolls_back_to_friday_close_and_mirrors_next_opening():
    saturday = _at(14, 12)
    assert previous_close(_SPACE, saturday) == _at(13, 17)
    assert next_opening(_SPACE, saturday) == _at(16, 9)


def test_a_schedule_that_never_opened_in_range_returns_none():
    closed = SimpleNamespace(timezone="UTC", opening_hours={"weekly": {"monday": []}, "exceptions": {}})
    assert previous_close(closed, _at(9, 20), days=30) is None
