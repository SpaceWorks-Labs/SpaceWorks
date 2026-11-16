"""Counts of membership creation, activation and revocation, with closing balances."""

from datetime import timedelta

from django.utils import timezone

from apps.accounts import rbac
from apps.makerspaces.models import MakerspaceMembership
from apps.operations.membership_report_history import active_at, membership_intervals
from apps.operations.membership_report_scope import report_queryset
from apps.operations.report_types import ReportResult
from apps.operations.reports_fg_common import calendar_periods, membership_window, scoped_spaces

FIELDS = ("period", "new_members", "activated_members", "revoked_members", "active_members")


def build_membership_growth(makerspace_id, *, limit=None, date_range=None, grain="day", now=None, actor=None):
    now = now or timezone.now()
    records = []
    action = rbac.Action.VIEW_AUDIT
    for space in scoped_spaces(makerspace_id, action, actor=actor, modules=("membership",)):
        created = list(report_queryset(MakerspaceMembership.objects.all(), space.pk, action, actor=actor)
                       .values_list("created_at", flat=True))
        if not created:
            continue
        intervals = membership_intervals(space, actor=actor, action=action)
        spans = [span for history in intervals.values() for span in history]
        first, last = membership_window(space, date_range, now, min(created))
        for period, left, right in calendar_periods(space, first, last, grain):
            row = dict(period=period, new_members=sum(left <= at < right for at in created),
                       activated_members=sum(left <= start < right for start, _ in spans),
                       revoked_members=sum(end is not None and left <= end < right for _, end in spans),
                       active_members=sum(active_at(history, right - timedelta(microseconds=1))
                                          for history in intervals.values()))
            if makerspace_id is None:
                row["makerspace_id"] = space.pk
            records.append(row)
    fields = (("makerspace_id",) + FIELDS) if makerspace_id is None else FIELDS
    return ReportResult(fields, records if limit is None else records[:limit], {
        "grain": grain, "definition": "Memberships created and lifecycle activations/revocations per local period; active memberships at period end.",
        "limitations": "Counts memberships, including staff, rather than distinct people across spaces. Legacy activation/revocation timestamps supplement lifecycle audits.",
    })
