"""How long a membership application waits for a decision: median and 90th percentile (parity O-B3, An2).

Per period (the decision's local month/week/day), for join REQUESTS (invitations have no wait): how many were
decided, how many approved and rejected, and the wait from submission to the decision in hours. The decision is
the approval instant, or for a rejection the decision instant. The percentile is nearest-rank (the smallest
wait with at least 90% of waits at or below it), so a single slow case is visible and never interpolated away.
Tenant-local: medians and percentiles cannot be rebuilt from other spaces' summaries.
"""

from math import ceil
from statistics import median

from django.utils import timezone

from apps.makerspaces.models import Makerspace, MembershipRequest
from apps.operations.report_types import ReportResult
from apps.operations.reports_fg_common import calendar_periods, membership_window

FIELDS = ("period", "decisions", "approved", "rejected", "median_hours", "p90_hours")


def p90(sorted_values):
    return sorted_values[ceil(0.9 * len(sorted_values)) - 1] if sorted_values else None


def _decisions(space, actor=None):
    from apps.makerspaces.member_unit_scope import narrow_by_unit_lookup

    rows = MembershipRequest.objects.filter(makerspace=space, kind=MembershipRequest.Kind.REQUEST)
    # parity O-B3: a unit-scoped actor sees the waits of their own unit's applicants only
    rows = narrow_by_unit_lookup(rows, actor, space.pk, "unit_choice__unit__path", "manage_members").values(
        "created_at", "approved_at", "decided_at", "state")
    for row in rows:
        if row["approved_at"]:
            yield row["created_at"], row["approved_at"], True
        elif row["state"] == MembershipRequest.State.REVOKED and row["decided_at"]:
            yield row["created_at"], row["decided_at"], False


def build_membership_approval_times(makerspace_id, *, limit=None, date_range=None, grain="month", now=None,
                                    actor=None, **_ignored):
    now, space = now or timezone.now(), Makerspace.objects.get(pk=makerspace_id)
    decisions = list(_decisions(space, actor))
    first = min((decided for _created, decided, _ok in decisions), default=now)
    records = []
    for period, left, right in calendar_periods(space, *membership_window(space, date_range, now, first), grain):
        inside = [(created, ok) for created, decided, ok in decisions if left <= decided < right]
        waits = sorted(max(0.0, (decided - created).total_seconds() / 3600) for created, decided, _ok in decisions
                       if left <= decided < right)
        records.append({"period": period, "decisions": len(inside), "approved": sum(ok for _c, ok in inside),
                        "rejected": sum(not ok for _c, ok in inside),
                        "median_hours": round(median(waits), 1) if waits else None,
                        "p90_hours": round(p90(waits), 1) if waits else None})
    return ReportResult(FIELDS, records if limit is None else records[:limit], {
        "grain": grain, "definition": "Join requests decided per period with the median and 90th-percentile wait "
                                      "from submission to the decision, in hours."})
