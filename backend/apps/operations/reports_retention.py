"""Join cohorts: mature anniversaries only, counts only, local calendar months."""

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.utils import timezone

from apps.accounts import rbac
from apps.makerspaces.local_time import to_local
from apps.operations.membership_report_history import active_at, membership_intervals
from apps.operations.report_types import ReportResult
from apps.operations.reports_fg_common import scoped_spaces
from apps.operations.reports_finance_sources import finance_window

FIELDS = (
    "cohort_month", "months_after_join", "cohort_members", "eligible_members",
    "retained_members", "retention_percent", "churned_members", "reactivated_members",
)


def build_member_retention(makerspace_id, *, limit=None, date_range=None, months=None, now=None, actor=None):
    now = now or timezone.now()
    observed = now
    records = []
    spaces = scoped_spaces(makerspace_id, rbac.Action.VIEW_AUDIT, actor=actor, modules=("membership",))
    for space in spaces:
        start, end = finance_window(space, date_range)
        observed = min(now, end - timedelta(microseconds=1)) if end else now
        cohorts = defaultdict(list)
        for intervals in membership_intervals(space, actor=actor).values():
            if not intervals:
                continue
            joined = intervals[0][0]
            if joined > observed or (start and joined < start):
                continue
            cohorts[to_local(space, joined).strftime("%Y-%m")].append(intervals)
        for cohort, members in sorted(cohorts.items()):
            for offset in ((months,) if months else (3, 6, 12)):
                eligible = retained = 0
                for intervals in members:
                    anniversary = to_local(space, intervals[0][0]) + relativedelta(months=offset)
                    if anniversary <= observed:
                        eligible += 1
                        retained += active_at(intervals, anniversary)
                row = {
                    "cohort_month": cohort, "months_after_join": offset,
                    "cohort_members": len(members), "eligible_members": eligible,
                    "retained_members": retained,
                    "retention_percent": (
                        (Decimal(retained * 100) / eligible).quantize(Decimal("0.01")) if eligible else None
                    ),
                    "churned_members": sum(any(end and end <= observed for _, end in spans) for spans in members),
                    "reactivated_members": sum(any(start <= observed for start, _ in spans[1:]) for spans in members),
                }
                if makerspace_id is None:
                    row["makerspace_id"] = space.pk
                records.append(row)
    fields = (("makerspace_id",) + FIELDS) if makerspace_id is None else FIELDS
    return ReportResult(fields, records if limit is None else records[:limit], {
        "definition": "Retained = active on the local calendar-month anniversary; immature memberships are excluded from the denominator. Organization totals count memberships, not distinct people.",
        "history": "Lifecycle audits, with membership timestamps for legacy rows; reasons and identities are omitted.",
        "observed_at": observed.isoformat(),
    })
