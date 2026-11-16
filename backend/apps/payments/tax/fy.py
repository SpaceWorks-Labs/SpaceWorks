"""Financial-year boundaries for document numbering and FY reports.

The per-space financial year belongs to lane L4 (`makerspaces.financial_year`, fixed
signatures `fy_bounds(makerspace, on_date) -> (start, end)` and `fy_label(...)`). This
module reads it when present. Until L4 merges, the fallback below applies L4's posted
default -- an April start (owner decision 71) or the space's
`financial_year_start_month` if that field already exists. Only the START date of L4's
bounds is used, so either end convention (inclusive or exclusive) reads the same.
"""

from datetime import date

try:  # pragma: no cover - exercised once L4 is merged
    from apps.makerspaces.financial_year import fy_bounds as _l4_bounds
except ImportError:  # pragma: no cover - until L4 merges
    _l4_bounds = None

DEFAULT_START_MONTH = 4


def _fallback_start(makerspace, on_date):
    month = int(getattr(makerspace, "financial_year_start_month", 0) or DEFAULT_START_MONTH)
    year = on_date.year if on_date.month >= month else on_date.year - 1
    return date(year, month, 1)


def fy_start(makerspace, on_date):
    if _l4_bounds is not None:
        start = _l4_bounds(makerspace, on_date)[0]
        return start.date() if hasattr(start, "date") and not isinstance(start, date) else start
    return _fallback_start(makerspace, on_date)


def fy_end_exclusive(start):
    return date(start.year + 1, start.month, 1)


def fy_short(start):
    """'26-27' for an April year, '26' for a calendar year: compact enough for Rule 46."""
    end = fy_end_exclusive(start)
    last_year = end.year if end.month > 1 else end.year - 1
    if last_year == start.year:
        return f"{start.year % 100:02d}"
    return f"{start.year % 100:02d}-{last_year % 100:02d}"


def fy_name(start):
    """'2026-27' or '2026', for reports and filters."""
    short = fy_short(start)
    return f"{start.year}" if "-" not in short else f"{start.year}-{short[-2:]}"
