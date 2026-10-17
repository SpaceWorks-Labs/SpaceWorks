"""Shared calendar, scope and output boundaries for inventory analytics."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone

from apps.makerspaces.platform import module_enabled
from apps.operations.report_types import ReportNotFound, ReportResult
from apps.operations.reports_common import apply_range, limited, period_expression, report_spaces
from apps.operations.reports_j_common import calendar_range


GRAINS = ("day", "week", "month")


def spaces(makerspace_id, *modules):
    return [space for space in report_spaces(makerspace_id, *modules)
            if all(module_enabled(space, module) for module in modules)]


def dated(queryset, field, space, date_range, grain):
    return apply_range(queryset, field, calendar_range(date_range, space)).annotate(
        report_period=period_expression(field, grain, makerspace=space),
    )


def bucket(value, space, grain):
    if grain not in GRAINS:
        raise ValueError("Unsupported report grain.")
    day = value.astimezone(ZoneInfo(space.timezone)).date() if isinstance(value, datetime) else value
    if grain == "week":
        return day - timedelta(days=day.weekday())
    return day.replace(day=1) if grain == "month" else day


def in_range(value, date_range):
    return value is not None and (not date_range or (
        (date_range[0] is None or value >= date_range[0])
        and (date_range[1] is None or value < date_range[1])))


def result(fields, records, makerspace_id, limit, *, identity=False, meta=None):
    if identity and makerspace_id is None:
        raise ReportNotFound()
    fields = tuple(fields)
    if makerspace_id is None:
        fields = ("makerspace_id", *fields)
    records = [{field: row.get(field) for field in fields} for row in records]
    return ReportResult(fields, limited(records, limit), meta or {})


def percent(numerator, denominator):
    return round(float(numerator / denominator * 100), 2) if denominator else None


def hours(start, end):
    return max(0, (end - start).total_seconds() / 3600)


def window(date_range):
    end = min(date_range[1], timezone.now()) if date_range and date_range[1] else timezone.now()
    return (date_range[0] if date_range else None), end


def histogram(value):
    for upper, label in ((1, "0–1h"), (24, "1–24h"), (72, "24–72h"), (168, "72–168h")):
        if value < upper:
            return label
    return "168h+"
