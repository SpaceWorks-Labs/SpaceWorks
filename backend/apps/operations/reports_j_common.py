"""Small shared primitives for the operational analytics builders."""

from datetime import datetime, time, timedelta, timezone as datetime_timezone
from zoneinfo import ZoneInfo

from apps.makerspaces.platform import module_enabled
from apps.operations.report_types import ReportResult
from apps.operations.reports_common import limited, report_spaces


def area_spaces(makerspace_id, *modules):
    # report_spaces resolves deployment eligibility; single-space calls still need
    # source gates, including direct builder calls from organization orchestration.
    return [space for space in report_spaces(makerspace_id, *modules)
            if all(module_enabled(space, module) for module in modules)]


def calendar_range(date_range, space=None):
    """Calendar labels use the report's zone; rolling windows retain instants.

    Shared views/schedules may parse dates before selecting a tenant. Rebinding
    their CalendarDateRange here keeps previews, downloads and organization
    builders on the same local boundaries without changing precise tuple windows.
    """
    from apps.operations.report_date_ranges import CalendarDateRange
    if not isinstance(date_range, CalendarDateRange):
        return date_range
    zone = ZoneInfo(space.timezone) if space else datetime_timezone.utc
    return tuple(datetime.combine(at.date(), time.min, tzinfo=zone) if at else None for at in date_range)


def period(at, grain, space=None):
    if grain not in ("day", "week", "month"):
        raise ValueError("Unsupported report grain.")
    day = at.astimezone(ZoneInfo(space.timezone)).date() if space else at.date()
    if grain == "week":
        day -= timedelta(days=day.weekday())
    elif grain == "month":
        day = day.replace(day=1)
    return day.isoformat()


def result(fields, records, makerspace_id, limit, **meta):
    fields = (("makerspace_id",) + fields) if makerspace_id is None else fields
    return ReportResult(fields, limited(records, limit), meta)


def rate(numerator, denominator):
    return round(numerator / denominator * 100, 2) if denominator else None


def chart(x, values, *, series=(), time=True, partition="tenant", currency=None, top=None):
    return {
        "series": list(series), "x": {"field": x, "kind": "time" if time else "category"},
        "values": [{"field": field, "unit": unit} for field, unit in values],
        "currency_field": currency, "partition": partition, "negatives": "clip",
        "truncation": {"top_n": top, "other_label": "Other"} if top else None,
        "alt_template": "{count} observations",
    }
