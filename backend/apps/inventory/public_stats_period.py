"""The public stats period and the small-number suppression every public count passes.

The period is FIXED by the space (#170): there is no visitor switcher. Windows are read on
the space's own wall clock, half-open `[start, end)` as aware instants; "all" has no start.
"fy" is the financial year from L4 (`makerspaces.financial_year.fy_bounds`).
"""

from dataclasses import dataclass
from datetime import date, datetime

from django.utils import timezone

from apps.makerspaces.local_time import local_day_bounds, to_local

SUPPRESS_BELOW = 3  # #170 [#165 auto]: a count below 3 could identify a person.


@dataclass(frozen=True)
class Window:
    key: str
    label: str
    start: datetime | None
    end: datetime | None
    now: datetime

    def until_now(self):
        """The window cut at now: what has already HAPPENED in the period."""
        return self.start, min(self.end, self.now) if self.end else self.now

    def payload(self):
        return {"key": self.key, "label": self.label,
                "start": self.start.isoformat() if self.start else None,
                "end": self.end.isoformat() if self.end else None}


def _span(makerspace, first, last):
    return local_day_bounds(makerspace, first)[0], local_day_bounds(makerspace, last)[1]


def period_window(makerspace, period, now=None):
    from apps.makerspaces.financial_year import fy_bounds, fy_label
    from apps.makerspaces.public_stats_settings import PERIODS

    now = now or timezone.now()
    today = _local_date(makerspace, now)
    if period == "all":
        return Window("all", PERIODS["all"], None, None, now)
    if period == "year":
        start, end = _span(makerspace, date(today.year, 1, 1), date(today.year, 12, 31))
        return Window("year", str(today.year), start, end, now)
    if period == "fy":
        first, last = fy_bounds(makerspace, today)
        start, end = _span(makerspace, first, last)
        return Window("fy", f"FY {fy_label(makerspace, today)}", start, end, now)
    first = today.replace(day=1)
    last = (date(first.year + 1, 1, 1) if first.month == 12 else date(first.year, first.month + 1, 1))
    start = local_day_bounds(makerspace, first)[0]
    end = local_day_bounds(makerspace, last)[0]
    return Window("month", first.strftime("%B %Y"), start, end, now)


def _local_date(makerspace, instant):
    return to_local(makerspace, instant).date()


def in_window(queryset, field, window, *, until_now=True):
    """Filter `field` into the window (cut at now unless `until_now=False`)."""
    start, end = window.until_now() if until_now else (window.start, window.end)
    if start is not None:
        queryset = queryset.filter(**{f"{field}__gte": start})
    if end is not None:
        queryset = queryset.filter(**{f"{field}__lt": end})
    return queryset


def suppressed(count):
    """`{"value", "suppressed"}`: a count below the threshold is never published."""
    count = int(count or 0)
    if count < SUPPRESS_BELOW:  # zero too: "fewer than 3" never tells 0 from 1 or 2
        return {"value": None, "suppressed": True}
    return {"value": count, "suppressed": False}
