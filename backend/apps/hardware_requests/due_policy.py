"""Loan due instants against the space's opening hours (research P1-4).

Every COMPUTED return due -- the issue default, a direct handout, a self-checkout and a
renewal -- passes through `effective_due`: one that falls while the space is closed
rolls forward to the next opening plus a fixed one-hour grace (decision 219b), capped
at that session's close, so reminders and overdue (which read the stored instant) never
fire for a time nobody can return, nor the minute the doors open. No space setting
changes the grace.
The computed accept-time pickup deadline uses `effective_pickup_deadline` instead and
rolls to the close of the next open session, so the reservation stays collectable.

A STAFF-ENTERED instant is stored exactly as given; `closed_notice` reports it so the
console can warn. The closing instant itself still counts as returnable ("back by
closing time"). A space with no hours recorded is always open: both are no-ops, as is
a schedule that never reopens (the instant is kept rather than dropped).
"""

from datetime import timedelta

from apps.makerspaces.opening_hours import has_hours, is_open, next_open_interval, next_opening

_EDGE = timedelta(microseconds=1)
RETURN_GRACE = timedelta(hours=1)


def _closed_at(makerspace, due):
    return (due is not None and has_hours(makerspace)
            and not is_open(makerspace, due) and not is_open(makerspace, due - _EDGE))


def effective_due(makerspace, due):
    """`due`, or the next opening + `RETURN_GRACE` (capped at that close) when closed at `due`."""
    if not _closed_at(makerspace, due):
        return due
    window = next_open_interval(makerspace, due)
    if window is None:
        return due
    opens, closes = max(due, window[0]), window[1]
    return min(opens + RETURN_GRACE, closes)


def effective_pickup_deadline(makerspace, deadline):
    """`deadline`, or the close of the next open session when the space is closed then.

    Unlike a return due, a pickup deadline that rolled only to the opening instant would
    expire the reservation before anyone could collect it.
    """
    if not _closed_at(makerspace, deadline):
        return deadline
    window = next_open_interval(makerspace, deadline)
    return deadline if window is None else window[1]


def closed_notice(makerspace, due):
    """None, or `{"code": "space_closed", "next_open_at": iso|None}` for a closed instant."""
    if not _closed_at(makerspace, due):
        return None
    opening = next_opening(makerspace, due)
    return {"code": "space_closed", "next_open_at": opening.isoformat() if opening else None}
