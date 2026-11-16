"""Domain blocks of the superadmin platform overview (#183A): the shared contract.

A block names its metrics and a gate (is the domain on in this space?), and its
collector returns ``{metric: {makerspace_id: value}}`` from GROUPED queries over the
spaces the gate admits. The platform total of a summable metric is then the sum of
those per-space values by construction, so the total always equals the breakdown.
Counts only: no collector selects a person's name, email, username or contact field.
"""

from dataclasses import dataclass, field

from django.db.models import Count, F, Sum


@dataclass(frozen=True)
class Metric:
    key: str
    label: str
    unit: str = "count"
    #: "snapshot" = state now (loans out); "period" = happened inside the window.
    timing: str = "period"

    @property
    def summable(self):
        return self.unit != "percent"


@dataclass(frozen=True)
class Block:
    key: str
    label: str
    #: Module keys (or capability keys) the gate reads; shown to the superadmin.
    switches: tuple
    gate: object  # callable(makerspace) -> bool
    metrics: tuple
    collect: object  # callable(ids, window, now) -> {metric: {space_id: value}}
    #: Deployment-wide numbers that belong to no single space (never per-space rows).
    platform_metrics: tuple = field(default=())
    collect_platform: object = None  # callable(window, now) -> {metric: value}
    #: callable(totals, per_space, window) -> {metric: value} for percent metrics.
    derive: object = None


def always_on(_space):
    return True


def in_window(queryset, field_name, window):
    if window.start is not None:
        queryset = queryset.filter(**{f"{field_name}__gte": window.start})
    return queryset.filter(**{f"{field_name}__lt": window.end})


def count_by_space(queryset, space_field="makerspace_id", *, distinct="pk"):
    rows = queryset.order_by().values(overview_space=F(space_field)).annotate(overview_n=Count(distinct, distinct=True))
    return {row["overview_space"]: row["overview_n"] for row in rows if row["overview_space"] is not None}


def sum_by_space(queryset, expression, space_field="makerspace_id"):
    rows = queryset.order_by().values(overview_space=F(space_field)).annotate(overview_v=Sum(expression))
    return {row["overview_space"]: row["overview_v"] or 0 for row in rows if row["overview_space"] is not None}


def hours(value):
    """Minutes or a timedelta, as hours rounded to 0.1 (a float the client can format)."""
    if value is None:
        return 0
    seconds = value.total_seconds() if hasattr(value, "total_seconds") else float(value) * 60
    return round(seconds / 3600, 1)

