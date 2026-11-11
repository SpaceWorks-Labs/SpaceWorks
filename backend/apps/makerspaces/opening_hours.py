"""Opening-hours arithmetic for work that only happens while the space is open.

Reusable on purpose (#142 OQ-11, #158): the machine-job ETA pushes attended work into
open hours, and machine sessions (L23) stop at closing time. Built on `local_time`, the
single local-day boundary service; a space with no hours recorded is always open, so
every function then reduces to plain clock arithmetic.

`makerspace` may be any object with `.timezone` and `.opening_hours`.
"""

from datetime import timedelta

from .local_time import _day_intervals, is_open, next_open_interval, to_local  # noqa: F401  (re-exported for callers)

MAX_INTERVALS = 400  # about a year of daily intervals; a closed schedule never loops forever


def has_hours(makerspace):
    hours = getattr(makerspace, "opening_hours", None) or {}
    return bool(hours.get("weekly") or hours.get("exceptions"))


def advance_open(makerspace, start, minutes):
    """The instant `minutes` of OPEN time after `start`, or None if the space never reopens."""
    minutes = max(float(minutes or 0), 0.0)
    if not has_hours(makerspace):
        return start + timedelta(minutes=minutes)
    cursor, remaining = start, timedelta(minutes=minutes)
    for _ in range(MAX_INTERVALS):
        window = next_open_interval(makerspace, cursor)
        if window is None:
            return None
        opens, closes = window
        cursor = max(cursor, opens)
        available = closes - cursor
        if remaining <= available:
            return cursor + remaining
        remaining -= available
        cursor = closes
    return None


def next_opening(makerspace, at):
    """`at` when open, else the next opening instant (None for a schedule that never opens)."""
    if not has_hours(makerspace):
        return at
    window = next_open_interval(makerspace, at)
    return None if window is None else max(at, window[0])


def closing_time(makerspace, at):
    """When the current open interval ends, or None (always open, or closed right now)."""
    if not has_hours(makerspace):
        return None
    window = next_open_interval(makerspace, at)
    if window is None or window[0] > at:
        return None
    return window[1]


def previous_close(makerspace, at, *, days=MAX_INTERVALS):
    """The latest closing instant at or before `at`; `at` itself when open (or no hours), None if none in range.

    The mirror of `next_opening` (#227 m14): a guest pass that ends while the space is closed
    caps its loans at the close of the last open session inside the pass window.
    """
    if not has_hours(makerspace) or is_open(makerspace, at):
        return at
    day = to_local(makerspace, at).date()
    for offset in range(days):
        past = [end for _, end in _day_intervals(makerspace, day - timedelta(days=offset)) if end <= at]
        if past:
            return max(past)
    return None
