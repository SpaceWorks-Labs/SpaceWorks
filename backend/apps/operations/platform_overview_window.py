"""Period presets for the superadmin platform overview (#183A).

Spaces sit in different time zones, so platform periods are UTC, like the other platform
analytics: "this month" starts at the first UTC midnight of the month, "this year" at
1 January UTC, "all time" has no start, and "custom" covers whole UTC days from `start`
to `end` inclusive. Every window ends no later than now.
"""

from django.utils.translation import gettext
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from django.utils import timezone
from rest_framework.exceptions import ValidationError

PRESETS = ("this_month", "this_year", "all_time", "custom")
#: A custom window may span at most this many days, so one request stays bounded.
MAX_CUSTOM_DAYS = 3660


@dataclass(frozen=True)
class OverviewWindow:
    preset: str
    start: datetime | None
    end: datetime

    @property
    def hours(self):
        """Length in hours, or None for all time (no capacity to measure against)."""
        if self.start is None:
            return None
        return max((self.end - self.start).total_seconds() / 3600, 0)

    def date_range(self):
        return (self.start, self.end)

    def cache_part(self):
        return f"{self.preset}:{self.start.isoformat() if self.start else '-'}:{self.end.date().isoformat()}"


def _midnight(day):
    return datetime.combine(day, time.min, tzinfo=UTC)


def _parse_day(raw, field):
    if not isinstance(raw, str) or len(raw) != 10:
        raise ValidationError({field: gettext("Use a date like 2026-01-31.")})
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise ValidationError({field: gettext("Use a date like 2026-01-31.")}) from None


def resolve_window(preset="this_month", start=None, end=None, *, now=None):
    """Validate the request's period and return it as a UTC window."""
    now = now or timezone.now()
    today = now.astimezone(UTC).date()
    if preset not in PRESETS:
        raise ValidationError({"period": gettext('Choose one of: {value}.').format(value=', '.join(PRESETS))})
    if preset != "custom" and (start or end):
        raise ValidationError({"period": gettext("Start and end dates are only used with the custom period.")})
    if preset == "this_month":
        return OverviewWindow(preset, _midnight(today.replace(day=1)), now)
    if preset == "this_year":
        return OverviewWindow(preset, _midnight(today.replace(month=1, day=1)), now)
    if preset == "all_time":
        return OverviewWindow(preset, None, now)
    first, last = _parse_day(start, "start"), _parse_day(end, "end")
    if last < first:
        raise ValidationError({"end": gettext("The end date must be on or after the start date.")})
    if first > today:
        raise ValidationError({"start": gettext("The start date cannot be in the future.")})
    if (last - first).days >= MAX_CUSTOM_DAYS:
        raise ValidationError({"end": gettext("Choose a period of ten years or less.")})
    return OverviewWindow(preset, _midnight(first), min(_midnight(last + timedelta(days=1)), now))
