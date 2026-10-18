"""Calendar and output primitives shared by booking and event measurements."""

from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from .report_types import ReportResult
from .reports_common import limited


def source_spaces(makerspace_id, module):
    from .reports_common import report_spaces
    return report_spaces(makerspace_id, module).filter(enabled_modules__contains=[module])


def report_window(space, date_range):
    from .reports_finance_sources import finance_window
    return finance_window(space, date_range)


def period_at(at, grain, space):
    local = at.astimezone(ZoneInfo(space.timezone))
    day = local.date()
    if grain == "week":
        day -= timedelta(days=day.weekday())
    elif grain == "month":
        day = day.replace(day=1)
    elif grain != "day":
        raise ValueError("Unsupported report grain.")
    return datetime.combine(day, datetime.min.time(), local.tzinfo)


def next_period(at, grain):
    if grain == "month":
        return at.replace(year=at.year + (at.month == 12), month=at.month % 12 + 1, day=1)
    return at + timedelta(days=7 if grain == "week" else 1)


def hours(start, end):
    # Subtraction in UTC measures elapsed hours even over local DST changes.
    return Decimal(str((end.astimezone(dt_timezone.utc) - start.astimezone(dt_timezone.utc)).total_seconds())) / 3600


def percent(numerator, denominator):
    return round(float(numerator / denominator * 100), 2) if denominator else None


def result(fields, records, makerspace_id, limit, *, meta=None):
    output = ("makerspace_id", *fields) if makerspace_id is None else fields
    if makerspace_id is not None:
        records = [{k: v for k, v in row.items() if k != "makerspace_id"} for row in records]
    return ReportResult(output, limited(records, limit), meta or {})


def histogram_bucket(value, edges, labels):
    return labels[next((i for i, edge in enumerate(edges) if value < edge), len(edges))]


def chart(x, values, *, series=(), time=False, currency=False, top=None, tenant=True, negatives=False):
    return {
        "series": list(series), "x": {"field": x, "kind": "time" if time else "category"},
        "values": [{"field": field, "unit": unit} for field, unit in values],
        "currency_field": "currency" if currency else None,
        "partition": "currency" if currency else ("tenant" if tenant else None),
        "negatives": "allow" if negatives else "clip",
        "truncation": {"top_n": top, "other_label": "Other"} if top else None,
        "alt_template": f"{{{values[0][0]}}} {values[0][1]} for {{{x}}}",
    }
