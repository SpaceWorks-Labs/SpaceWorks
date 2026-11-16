"""Shared shape for the release-0.12 metric tables: ``metric`` / ``value`` rows, counts only.

Each builder describes ONE makerspace as ``(metric, value)`` pairs over a window. The same code
serves the tenant report and the superadmin roll-up: with no makerspace id every eligible space
contributes its own rows, tagged with ``makerspace_id``, so a roll-up is per-space aggregates
and never a cross-tenant row of personal data (nothing here names a person).
"""

from datetime import timedelta

from django.utils import timezone

from apps.operations.reports_j_common import area_spaces, calendar_range, result

FIELDS = ("metric", "value")
DEFAULT_DAYS = 30


def window(date_range, space, now=None):
    """The report window as ``(start, end)``: a missing bound means "the last 30 days to now"."""
    now = now or timezone.now()
    start, end = calendar_range(date_range, space) or (None, None)
    end = end or now
    return (start or end - timedelta(days=DEFAULT_DAYS)), end


def metric_report(makerspace_id, modules, per_space, *, limit=None, date_range=None, **meta):
    records = []
    for space in area_spaces(makerspace_id, *modules):
        start, end = window(date_range, space)
        for metric, value in per_space(space, start, end):
            row = {"metric": metric, "value": value}
            records.append({"makerspace_id": space.pk, **row} if makerspace_id is None else row)
    meta.setdefault("period", "The chosen dates, or the last 30 days when none are given.")
    return result(FIELDS, records, makerspace_id, limit, **meta)
