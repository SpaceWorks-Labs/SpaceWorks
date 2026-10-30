"""The makerspace's financial year (owner decision 71: per space, April by default).

One source of truth for "which financial year is this date in", read by membership FY
plans (L4) and by document numbering (L5). The two public signatures are FIXED -- other
lanes call them:

* ``fy_bounds(makerspace, on_date) -> (start, end)``: the first and the LAST calendar day
  (both inclusive, ``datetime.date``) of the financial year containing ``on_date``.
* ``fy_label(makerspace, on_date) -> str``: ``"2026-27"`` for a year that spans two
  calendar years, ``"2026"`` when the year starts in January.

``on_date`` may be a ``date`` or an aware ``datetime``; a datetime is read on the
makerspace's own wall clock first, so a payment at 23:30 local time on 31 March belongs
to the year that ends that day wherever the server runs.
"""

from datetime import date, datetime, timedelta

from dateutil.relativedelta import relativedelta

DEFAULT_START_MONTH = 4
# A finance setting (LANE-RULES §13): the Space Manager's alone, never delegable.
SETTING_MODULE, SETTING_KEY = "finance", "finance.financial_year_start_month"


def start_month(makerspace):
    month = getattr(makerspace, "financial_year_start_month", None) or DEFAULT_START_MONTH
    return month if 1 <= month <= 12 else DEFAULT_START_MONTH


def _local_date(makerspace, on_date):
    if isinstance(on_date, datetime):
        from apps.makerspaces.local_time import to_local
        return to_local(makerspace, on_date).date()
    return on_date


def fy_bounds(makerspace, on_date):
    """``(start, end)`` dates, both inclusive, of the financial year containing ``on_date``."""
    day = _local_date(makerspace, on_date)
    month = start_month(makerspace)
    year = day.year if day.month >= month else day.year - 1
    start = date(year, month, 1)
    return start, start + relativedelta(years=1) - timedelta(days=1)


def fy_label(makerspace, on_date):
    start, end = fy_bounds(makerspace, on_date)
    if start.year == end.year:
        return str(start.year)
    return f"{start.year}-{str(end.year)[-2:]}"


def fy_end_at(makerspace, on_date):
    """The aware instant the financial year containing ``on_date`` ends: local midnight
    after its last day. Membership FY terms end exactly here (half-open)."""
    from apps.makerspaces.local_time import local_day_bounds
    _, end = fy_bounds(makerspace, on_date)
    return local_day_bounds(makerspace, end)[1]


def fy_start_at(makerspace, on_date):
    from apps.makerspaces.local_time import local_day_bounds
    start, _ = fy_bounds(makerspace, on_date)
    return local_day_bounds(makerspace, start)[0]


def fy_presets(makerspace, today, *, count=3):
    """The current and previous ``count - 1`` financial years as report filter presets:
    ``[{"key": "fy-2026-27", "label": "FY 2026-27", "start": date, "end": date}, ...]``."""
    presets = []
    anchor = _local_date(makerspace, today)
    for _ in range(max(count, 1)):
        start, end = fy_bounds(makerspace, anchor)
        label = fy_label(makerspace, anchor)
        presets.append({"key": f"fy-{label}", "label": f"FY {label}", "start": start, "end": end})
        anchor = start - timedelta(days=1)
    return presets

