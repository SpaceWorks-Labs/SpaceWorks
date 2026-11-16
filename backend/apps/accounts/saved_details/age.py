"""Calendar age only: birth dates are stored, computed ages never are.

A February 29 birthday advances on March 1 in a non-leap year. This matches
the completed-calendar-years rule without treating February 28 as a birthday.
"""

from datetime import date, datetime


def validate_dob(value, *, today=None):
    """Accept an ISO date/date, reject future dates, with no age admission rule."""
    if isinstance(value, datetime):
        raise ValueError("Use an ISO calendar birth date.")
    if isinstance(value, str):
        if len(value) != 10:
            raise ValueError("Use an ISO calendar birth date.")
        try:
            parsed = date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("Use a valid calendar birth date.") from exc
        if parsed.isoformat() != value:
            raise ValueError("Use an ISO calendar birth date.")
        value = parsed
    if type(value) is not date:
        raise ValueError("Use an ISO calendar birth date.")
    if value > (today or date.today()):
        raise ValueError("Birth date cannot be in the future.")
    return value


def age_on(dob, local_event_start_date):
    """Compute completed years as of the supplied event-local calendar date."""
    if type(local_event_start_date) is not date:
        raise ValueError("Use an event-local calendar date.")
    dob = validate_dob(dob)
    return local_event_start_date.year - dob.year - (
        (local_event_start_date.month, local_event_start_date.day) < (dob.month, dob.day)
    )
