"""Count-only dimensions and organization arithmetic for communications/mobile."""

from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Case, CharField, Count, Value, When

from .report_types import ReportResult
from .reports_common import apply_range, limited, period_expression


def category(field, allowed):
    """Project a closed vocabulary; never echo arbitrary audit/provider text."""
    return Case(*[When(**{field: value}, then=Value(value)) for value in allowed],
                default=Value("unknown"), output_field=CharField())


def buckets(queryset, field, space, grain, date_range, dimensions=(), **measures):
    return (apply_range(queryset, field, date_range).order_by()
            .annotate(period=period_expression(field, grain, makerspace=space))
            .values("period", *dimensions).annotate(count=Count("pk"), **measures))


def percent(numerator, denominator):
    if not denominator:
        return None
    return (Decimal(numerator) * 100 / Decimal(denominator)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP,
    )


def ratio(numerator, denominator):
    """Fractional rates use the same rounding on tenant and organization paths."""
    if not denominator:
        return None
    return (Decimal(numerator) / Decimal(denominator)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def result(fields, records, aggregate, limit, **meta):
    order = (("makerspace_id",) + fields) if aggregate else fields
    return ReportResult(order, limited(records, limit), meta)


def combine_counts(rows_by_space, *, limit, groups, counts, rates=(), latest=()):
    """Recompute rates from full summed inputs, preserving every chart dimension."""
    combined = {}
    for _space_id, rows in rows_by_space:
        for row in rows:
            key = tuple(row.get(field) for field in groups)
            target = combined.setdefault(key, {
                **{field: row.get(field) for field in groups},
                **dict.fromkeys(counts, 0), **dict.fromkeys(latest),
            })
            for field in counts:
                target[field] += row.get(field) or 0
            for field in latest:
                value = row.get(field)
                if value is not None and (target[field] is None or value > target[field]):
                    target[field] = value
    records = sorted(combined.values(), key=lambda row: tuple(str(row.get(f) or "") for f in groups))
    for row in records:
        for field, numerator, denominator in rates:
            row[field] = percent(row[numerator], row[denominator])
    return limited(records, limit)
