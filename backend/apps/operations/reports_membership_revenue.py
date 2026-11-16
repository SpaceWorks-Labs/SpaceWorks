"""Recurring-plan projection at each local period end, independent of payment rails."""

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from apps.accounts import rbac
from apps.audit.models import AuditLog
from apps.makerspaces.models import MembershipTerm
from apps.operations.membership_report_history import membership_intervals
from apps.operations.membership_report_scope import report_queryset
from apps.operations.report_types import ReportResult
from apps.operations.reports_fg_common import calendar_periods, membership_window, scoped_spaces
from apps.payments.models import Payment

FIELDS = ("period", "currency", "plan_id", "plan_name", "recurring_members", "mrr", "arr", "arpu", "churned_members", "reactivated_members")


def build_membership_revenue(makerspace_id, *, limit=None, date_range=None, grain="month", now=None, actor=None):
    now = now or timezone.now()
    records = []
    spaces = scoped_spaces(makerspace_id, rbac.Action.VIEW_FINANCE, actor=actor, modules=("membership",))
    for space in spaces:
        records.extend(_space_rows(space, date_range, now, makerspace_id is None, actor, grain))
    fields = (("makerspace_id",) + FIELDS) if makerspace_id is None else FIELDS
    return ReportResult(fields, records if limit is None else records[:limit], {
        "grain": grain, "definition": "Period-end recurring-plan projection: monthly price or yearly price / 12, per plan and currency; ARR = MRR * 12; ARPU = MRR / recurring memberships.",
        "limitations": "Uses current plan prices and current waiver state; no historical price snapshots exist. Custom-day plans and waived term charges are excluded. Churn/reactivation count recurring coverage gaps.",
    })


def _space_rows(space, date_range, now, aggregate, actor, grain):
    action = rbac.Action.VIEW_FINANCE
    terms = list(report_queryset(
        MembershipTerm.objects.filter(plan__makerspace=space, plan__interval__in=["monthly", "yearly"]),
        space.pk, action, actor=actor, field="membership__makerspace_id",
    ).values("id", "membership_id", "starts_at", "ends_at", "status", "plan__interval", "plan__amount", "plan__currency", "plan_id", "plan__name"))
    waived = set(report_queryset(Payment.objects.filter(
        subject_type=Payment.SubjectType.MEMBERSHIP_TERM, status=Payment.Status.WAIVED,
    ), space.pk, action, actor=actor).values_list("subject_id", flat=True))
    cancellations = dict(report_queryset(AuditLog.objects.filter(
        target_type="makerspaces.membershipterm", action="membership.term_cancelled",
    ), space.pk, action, actor=actor).order_by("created_at").values_list("target_id", "created_at"))
    memberships = membership_intervals(space, actor=actor, action=action)
    coverage = defaultdict(list)
    for term in terms:
        if term["id"] in waived:
            continue
        end = term["ends_at"]
        if term["status"] == "cancelled":
            cancelled = cancellations.get(str(term["id"]))
            if cancelled is None:
                continue  # No timestamp: historical coverage cannot be established.
            end = min(end, cancelled)
        price = term["plan__amount"] / (12 if term["plan__interval"] == "yearly" else 1)
        for start, stopped in memberships.get(term["membership_id"], []):
            left, right = max(start, term["starts_at"]), min(stopped or end, end)
            if left < right:
                coverage[(term["plan__currency"], term["membership_id"])].append(
                    (left, right, price, term["id"], term["plan_id"], term["plan__name"]))
    if not coverage:
        return []
    first, last = membership_window(space, date_range, now, min(t[0] for spans in coverage.values() for t in spans))
    rows = []
    for period, left, right in calendar_periods(space, first, last, grain):
        snapshot = right - timedelta(microseconds=1)
        by_plan = defaultdict(lambda: {"prices": [], "churn": 0, "reactivation": 0})
        for (currency, _member), spans in coverage.items():
            for span in spans:
                by_plan[(currency, span[4], span[5])]
            live = [span for span in spans if span[0] <= snapshot < span[1]]
            if live:
                # Overlapping terms count a member once: the latest starting term wins.
                chosen = max(live, key=lambda t: (t[0], t[3]))
                by_plan[(currency, chosen[4], chosen[5])]["prices"].append(chosen[2])
            merged = []
            for start, end, *_ in sorted(spans):
                if merged and start <= merged[-1][1]:
                    merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
                else:
                    merged.append((start, end))
            # A plan switch with continuous coverage is not a churn/reactivation.
            churned, reactivated = set(), set()
            for _, end in merged:
                if left <= end < right:
                    chosen = max((s for s in spans if s[1] == end), key=lambda s: (s[0], s[3]))
                    churned.add((currency, chosen[4], chosen[5]))
            for start, _ in merged[1:]:
                if left <= start < right:
                    chosen = max((s for s in spans if s[0] == start), key=lambda s: s[3])
                    reactivated.add((currency, chosen[4], chosen[5]))
            for key in churned:
                by_plan[key]["churn"] += 1
            for key in reactivated:
                by_plan[key]["reactivation"] += 1
        for (currency, plan_id, plan_name), values in sorted(by_plan.items()):
            count = len(values["prices"])
            mrr = sum(values["prices"], Decimal(0))
            cent = Decimal("0.01")
            row = {"period": period, "currency": currency, "plan_id": plan_id, "plan_name": plan_name, "recurring_members": count,
                   "mrr": mrr.quantize(cent), "arr": (mrr * 12).quantize(cent),
                   "arpu": (mrr / count if count else Decimal(0)).quantize(cent),
                   "churned_members": values["churn"], "reactivated_members": values["reactivation"]}
            if aggregate:
                row["makerspace_id"] = space.pk
            rows.append(row)
    return rows
