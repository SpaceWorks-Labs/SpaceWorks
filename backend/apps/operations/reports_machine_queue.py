"""Observed queue stage durations; no estimate for unfinished stages."""

from collections import defaultdict
from decimal import Decimal

from .reports_common import apply_range, period_expression
from .reports_machine_common import requests, result, spaces

FIELDS = ("period", "queue_id", "queue_name", "bucket_id", "stage", "samples", "median_minutes", "p90_minutes", "p95_minutes")
STAGES = (("created_at", "accepted_at"), ("accepted_at", "started_at"),
          ("started_at", "completed_at"), ("completed_at", "collected_at"))


def percentile(values, fraction):
    """Continuous linear percentile (same interpolation as percentile_cont)."""
    values = sorted(values)
    position = Decimal(len(values) - 1) * Decimal(str(fraction))
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    return values[lower] + (values[upper] - values[lower]) * (position - lower)


def build_service_queue_times(makerspace_id, *, limit=None, date_range=None, grain="day", actor=None):
    rows = []
    for space, scope in spaces(makerspace_id, ("machines", "machine_service"), actor):
        for lower, upper in STAGES:
            groups = defaultdict(list)
            qs = apply_range(requests(space, scope).filter(**{f"{lower}__isnull": False, f"{upper}__isnull": False}), upper, date_range)
            for row in qs.annotate(period=period_expression(upper, grain, makerspace=space)).values(
                "makerspace_id", "period", "queue_id", "queue__name", "bucket_id", "bucket__name", lower, upper,
            ).iterator():
                duration = Decimal(str((row[upper] - row[lower]).total_seconds())) / 60
                if duration < 0:
                    continue
                key = (row["makerspace_id"], row["period"].date().isoformat(), row["queue_id"], row["queue__name"] or row["bucket__name"], row["bucket_id"])
                groups[key].append(duration)
            for (space_id, period, queue_id, name, bucket_id), values in sorted(groups.items(), key=lambda item: str(item[0])):
                rows.append({"makerspace_id": space_id, "period": period, "queue_id": queue_id, "queue_name": name,
                             "bucket_id": bucket_id, "stage": f"{lower.removesuffix('_at')}→{upper.removesuffix('_at')}",
                             "samples": len(values), "median_minutes": percentile(values, .5),
                             "p90_minutes": percentile(values, .9), "p95_minutes": percentile(values, .95)})
    return result(FIELDS, rows, makerspace_id, limit, definition="Observed nonnegative stage durations in minutes, bucketed at each stage's end; percentiles interpolate continuously. Failed/incomplete stages without endpoints are not samples.")
