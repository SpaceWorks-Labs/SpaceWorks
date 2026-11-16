"""Decision 223 (k), lane L3b: the attendee to guest to joined funnel report (`join-funnel`).

One row per space (and one per month when the grain is month). Counts are distinct people, so the
deployment aggregate is not summable across spaces (listed in `org_report_scope`). A space whose
`membership.join_funnel` switch is off contributes no row.
"""
from datetime import datetime, timedelta

from django.utils import timezone

from apps.makerspaces.community_policy import funnel_on
from apps.makerspaces.join_funnel import funnel_counts
from apps.operations.report_types import ReportResult
from apps.operations.reports_common import limited, report_spaces

FIELDS = ("period", "attendees", "guests", "joined", "guest_rate_percent", "join_rate_percent")


def _percent(part, whole):
    return round(100.0 * part / whole, 1) if whole else 0.0


def _buckets(date_range, grain):
    start, end = date_range if date_range else (None, None)
    if grain != "month" or start is None or end is None:
        return [(start, end)]
    buckets, cursor = [], start
    while cursor < end:
        nxt = (cursor.replace(day=1) + timedelta(days=32)).replace(day=1)
        buckets.append((cursor, min(nxt, end)))
        cursor = nxt
    return buckets[:60]


def build_join_funnel(makerspace_id, *, limit=None, date_range=None, grain="day"):
    aggregate = makerspace_id is None
    records = []
    for space in report_spaces(makerspace_id, "membership"):
        if not funnel_on(space):
            continue
        for start, end in _buckets(date_range, grain):
            counts = funnel_counts(space, start, end)
            row = {"period": start.date() if isinstance(start, datetime) else None, **counts,
                   "guest_rate_percent": _percent(counts["guests"], counts["attendees"]),
                   "join_rate_percent": _percent(counts["joined"], counts["attendees"])}
            if aggregate:
                row["makerspace_id"] = space.pk
            records.append(row)
    fields = (("makerspace_id",) + FIELDS) if aggregate else FIELDS
    return ReportResult(fields, limited(records, limit))
