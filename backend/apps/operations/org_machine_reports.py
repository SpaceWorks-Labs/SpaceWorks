"""Machine roll-ups retain period, type, measurement and machine partitions."""

from functools import partial


def combine(rows_by_space, *, limit, groups, additive, rates=()):
    totals = {}
    for space_id, rows in rows_by_space:
        for row in rows:
            key = tuple(row.get(field) for field in groups)
            if key not in totals:
                totals[key] = {**row, **dict.fromkeys(additive, 0)}
            target = totals[key]
            for field in additive:
                target[field] += row.get(field) or 0
    for target in totals.values():
        target.pop("makerspace_id", None)
        for field, numerator, denominator, factor in rates:
            bottom = sum(target.get(key) or 0 for key in denominator)
            target[field] = round(float((target.get(numerator) or 0) / bottom * factor), 2) if bottom else None
    ordered = sorted(totals.values(), key=lambda row: tuple(str(row.get(field) or "") for field in groups))
    return ordered if limit is None else ordered[:limit]


USAGE_GROUPS = ("period", "measure", "machine_id", "machine_type_id")
SERVICE_GROUPS = ("period", "row_kind", "machine_id", "measurement", "product_id", "product_label", "outcome")
SERVICE_ADDITIVE = (
    "submitted", "accepted", "in_progress", "completed", "collected", "rejected", "failed",
    "request_count", "completed_count", "failed_count", "completed_hours", "failed_partial_hours",
    "total_recorded_service_hours", "completed_amount", "failed_partial_amount", "total_used",
    "failed_count_amount", "failed_grams_amount",
)
COMBINERS = {
    "machine-usage": partial(combine, groups=USAGE_GROUPS, additive=("entries", "service_hours", "manual_hours", "booked_hours")),
    "machine-downtime": partial(combine, groups=("period", "machine_id", "status"), additive=("status_hours",)),
    "machine-service": partial(combine, groups=SERVICE_GROUPS, additive=SERVICE_ADDITIVE,
                               rates=(("failure_rate", "failed_count", ("completed_count", "failed_count"), 100),)),
    "maintenance-activity": partial(combine, groups=("period", "machine_id"),
                                    additive=("log_count", "costed_log_count", "total_cost", "active_schedules", "overdue_schedules", "_interval_total_days", "_interval_gap_count"),
                                    rates=(("average_cost", "total_cost", ("costed_log_count",), 1),
                                           ("average_interval_days", "_interval_total_days", ("_interval_gap_count",), 1))),
    "printer-jobs": partial(combine, groups=("period", "machine_id", "state", "outcome"), additive=("job_count",)),
    "machine-errors": partial(combine, groups=("period", "machine_id", "severity"), additive=("error_count",)),
    "warranty-expiry": partial(combine, groups=("warranty_id",), additive=()),
}
