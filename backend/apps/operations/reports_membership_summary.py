"""The monthly staff membership summary (X33), as a schedulable report.

One row per metric for the previous local calendar month: members in good standing at
its start and end, joins, returns, lapses, revocations, terms due next month, renewal
charges collected, and open join requests. Counts only -- no person appears -- so it
is safe to email to every opted-in staff member through the scheduled-report delivery.
"""
from datetime import timedelta

from django.utils import timezone

from apps.makerspaces.models import Makerspace, MembershipRequest
from apps.operations.report_types import ReportResult
from apps.operations.reports_membership_l4_terms import build_membership_bridge, build_membership_renewals

FIELDS = ("metric", "value")


def _previous_month(space, now):
    from apps.makerspaces.local_time import local_day_bounds, to_local
    first_this = to_local(space, now).date().replace(day=1)
    first_last = (first_this - timedelta(days=1)).replace(day=1)
    return local_day_bounds(space, first_last)[0], local_day_bounds(space, first_this)[0]


def build_membership_monthly_summary(makerspace_id, *, limit=None, date_range=None, now=None, actor=None):
    now = now or timezone.now()
    space = Makerspace.objects.get(pk=makerspace_id)
    start, end = _previous_month(space, now)
    bridge = build_membership_bridge(makerspace_id, date_range=(start, end), grain="month", now=now).records
    totals = {key: sum(row[key] for row in bridge) for key in ("joined", "came_back", "lapsed", "revoked")}
    renewals = build_membership_renewals(makerspace_id, date_range=(start, end), grain="month", now=now).records
    rows = [
        {"metric": "members_at_start", "value": bridge[0]["start"] if bridge else 0},
        *({"metric": key, "value": value} for key, value in totals.items()),
        {"metric": "members_at_end", "value": bridge[-1]["end"] if bridge else 0},
        {"metric": "terms_due", "value": sum(row["due"] for row in renewals)},
        {"metric": "terms_renewed", "value": sum(row["renewed"] for row in renewals)},
        {"metric": "renewal_charges_collected", "value": sum(row["charges_collected"] for row in renewals)},
        {"metric": "open_join_requests", "value": MembershipRequest.objects.filter(
            makerspace=space, kind=MembershipRequest.Kind.REQUEST,
            state__in=("requested", "awaiting_vouches", "awaiting_payment")).count()},
    ]
    return ReportResult(FIELDS, rows if limit is None else rows[:limit], {
        "period_start": start.isoformat(), "period_end": end.isoformat(),
        "definition": "Membership in the previous calendar month, in counts."})
