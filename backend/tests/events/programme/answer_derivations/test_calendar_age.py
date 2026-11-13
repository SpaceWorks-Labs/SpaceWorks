"""Informational calendar arithmetic has no minimum/maximum age policy."""

from datetime import date, datetime

import pytest

from apps.accounts.saved_details.age import age_on, validate_dob


@pytest.mark.parametrize(("dob", "as_of", "expected"), [
    ("2004-05-12", date(2026, 12, 1), 22),
    ("2004-05-12", date(2026, 5, 11), 21),
    ("2004-05-12", date(2026, 5, 12), 22),
    ("2004-02-29", date(2025, 2, 28), 20),
    ("2004-02-29", date(2025, 3, 1), 21),
    ("2004-02-29", date(2024, 2, 29), 20),
    ("2004-12-31", date(2026, 1, 1), 21),
    ("2020-01-01", date(2026, 1, 1), 6),
    ("1900-01-01", date(2026, 1, 1), 126),
    ("2020-01-01", date(2019, 12, 31), -1),
])
def test_completed_calendar_years(dob, as_of, expected):
    assert age_on(dob, as_of) == expected


@pytest.mark.parametrize("value", ["2004-2-29", "2003-02-29", "2004-05-12T00:00:00", "2050-01-01", 22, True, None, datetime(2004, 5, 12)])
def test_invalid_or_future_dob_is_not_a_numeric_age(value):
    with pytest.raises(ValueError):
        validate_dob(value, today=date(2026, 10, 18))


def test_newborn_and_valid_very_old_dob_are_accepted_without_classification():
    assert validate_dob("2026-10-18", today=date(2026, 10, 18)) == date(2026, 10, 18)
    assert validate_dob("1800-01-01", today=date(2026, 10, 18)) == date(1800, 1, 1)


def test_event_date_is_a_calendar_date_not_an_implicit_utc_timestamp():
    with pytest.raises(ValueError):
        age_on("2004-05-12", datetime(2026, 12, 1))
