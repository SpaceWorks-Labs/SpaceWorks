"""Membership insights and the register export (G19, X14, X34).

Tenant-local builders (the view checked the reader's action first). Two are person
lists and therefore identity-bearing (a superadmin needs an open PII window): the
win-back list and the member register. The rest are counts.
"""
from datetime import timedelta
from statistics import median

from django.utils import timezone

from apps.makerspaces.models import Makerspace, MakerspaceMembership, MembershipRequest, MembershipTerm
from apps.operations.report_types import ReportResult
from apps.operations.reports_fg_common import calendar_periods, membership_window
from apps.operations.reports_membership_l4_terms import coverage


def _space(makerspace_id):
    return Makerspace.objects.get(pk=makerspace_id)


def _latest_terms(space):
    latest = {}
    for term in (MembershipTerm.objects.filter(membership__makerspace=space).exclude(status="cancelled")
                 .select_related("plan").order_by("membership_id", "-ends_at", "-pk")):
        latest.setdefault(term.membership_id, term)
    return latest


def _standing(term, now):
    if term is None:
        return "no_term"
    from apps.makerspaces.membership_term_history import standing
    value = standing(term, now)
    if value == "active" and not term.is_lifetime and term.ends_at <= now + timedelta(days=30):
        return "ending_soon"
    return value


BREAKDOWN_FIELDS = ("dimension", "value", "members")


def build_membership_breakdown(makerspace_id, *, limit=None, date_range=None, now=None, actor=None):
    now, space = now or timezone.now(), _space(makerspace_id)
    members = list(MakerspaceMembership.objects.filter(makerspace=space, status="active", user__account_kind="member"))
    latest = _latest_terms(space)
    from apps.makerspaces.models import MembershipRecord
    recorded = set(MembershipRecord.objects.filter(makerspace=space).exclude(state_code="").values_list(
        "membership_id", flat=True))
    counts = {}

    def add(dimension, value):
        counts[(dimension, value)] = counts.get((dimension, value), 0) + 1

    for member in members:
        term = latest.get(member.pk)
        add("plan", term.plan.name if term else "No plan")
        add("join_source", member.source or "unknown")
        years = (now - (member.created_at or now)).days / 365.25
        add("tenure", "under 1 year" if years < 1 else "1-2 years" if years < 2 else "2-5 years" if years < 5 else "5+ years")
        if member.member_number is None:
            add("record_gaps", "no member number")
        if term is None:
            add("record_gaps", "no term")
        if member.pk not in recorded:
            add("record_gaps", "no state code")
    rows = [{"dimension": d, "value": v, "members": n} for (d, v), n in sorted(counts.items())]
    return ReportResult(BREAKDOWN_FIELDS, rows if limit is None else rows[:limit], {
        "definition": "Active members by plan, how they joined, tenure, and missing record details.",
        "limitations": "Tenure counts from the first time the person joined this space."})


EXPIRY_FIELDS = ("week_start", "terms_ending", "renewal_amount", "currency")


def build_membership_expiry_calendar(makerspace_id, *, limit=None, date_range=None, now=None, actor=None):
    from apps.makerspaces.local_time import local_day_bounds, to_local
    now, space = now or timezone.now(), _space(makerspace_id)
    monday = to_local(space, now).date() - timedelta(days=to_local(space, now).weekday())
    terms = [term for term in _latest_terms(space).values() if term.status == "active" and not term.is_lifetime]
    rows = []
    for week in range(13):
        day = monday + timedelta(weeks=week)
        left, right = local_day_bounds(space, day)[0], local_day_bounds(space, day + timedelta(days=7))[0]
        groups = {}
        for term in terms:
            if left <= term.ends_at < right:
                groups.setdefault(term.currency or term.plan.currency, []).append(term)
        for currency, due in sorted(groups.items()) or [("", [])]:
            rows.append({"week_start": day.isoformat(), "terms_ending": len(due), "currency": currency,
                         "renewal_amount": sum((term.plan.renewal_price for term in due), 0)})
    return ReportResult(EXPIRY_FIELDS, rows if limit is None else rows[:limit], {
        "definition": "Current terms ending in each of the next 13 weeks and their renewal amount."})


WINBACK_FIELDS = ("membership_id", "member_number", "name", "email", "plan", "lapsed_at")


def build_membership_win_back(makerspace_id, *, limit=None, date_range=None, now=None, actor=None):
    now, space = now or timezone.now(), _space(makerspace_id)
    since = now - timedelta(days=180)
    lapsed = {}
    for membership_id, spans in coverage(space, now).items():
        last = spans[-1]
        if last[2] == "lapsed" and last[1] >= since:
            lapsed[membership_id] = last[1]
    latest = _latest_terms(space)
    from apps.makerspaces.membership_number import formatted, pattern_for
    pattern = pattern_for(space)
    rows = []
    for member in (MakerspaceMembership.objects.filter(pk__in=lapsed, status="active").select_related("user")
                   .order_by("pk")):
        term = latest.get(member.pk)
        rows.append({"membership_id": member.pk, "member_number": formatted(member.member_number, pattern,
                                                                            member.created_at.year),
                     "name": member.user.display_name, "email": member.user.email,
                     "plan": term.plan.name if term else "", "lapsed_at": lapsed[member.pk]})
    rows.sort(key=lambda row: row["lapsed_at"], reverse=True)
    return ReportResult(WINBACK_FIELDS, rows if limit is None else rows[:limit], {
        "definition": "Members whose membership lapsed in the last 180 days and who have not renewed."})


REGISTER_FIELDS = ("member_number", "name", "email", "plan", "standing", "term_ends_at", "source", "joined_at")


def build_member_register(makerspace_id, *, limit=None, date_range=None, now=None, actor=None, standing=None):
    now, space = now or timezone.now(), _space(makerspace_id)
    latest = _latest_terms(space)
    from apps.makerspaces.membership_number import formatted, pattern_for
    pattern = pattern_for(space)
    rows = []
    for member in (MakerspaceMembership.objects.filter(makerspace=space, status="active", user__account_kind="member")
                   .select_related("user").order_by("member_number", "pk")):
        term = latest.get(member.pk)
        value = _standing(term, now)
        if standing and value != standing:
            continue
        rows.append({"member_number": formatted(member.member_number, pattern, member.created_at.year),
                     "name": member.user.display_name, "email": member.user.email,
                     "plan": term.plan.name if term else "", "standing": value,
                     "term_ends_at": None if term is None or term.is_lifetime else term.ends_at,
                     "source": member.source, "joined_at": member.created_at})
    return ReportResult(REGISTER_FIELDS, rows if limit is None else rows[:limit], {
        "definition": "Active members with their plan, standing (active, ending soon, in grace, lapsed) and source."})


FUNNEL_FIELDS = ("period", "submitted", "approved", "activated", "rejected", "median_hours_to_approve",
                 "p90_hours_to_approve")


def build_membership_applications_funnel(makerspace_id, *, limit=None, date_range=None, grain="month", now=None,
                                         actor=None):
    now, space = now or timezone.now(), _space(makerspace_id)
    rows = list(MembershipRequest.objects.filter(makerspace=space, kind=MembershipRequest.Kind.REQUEST).values(
        "created_at", "approved_at", "decided_at", "state"))
    first = min((row["created_at"] for row in rows), default=now)
    records = []
    for period, left, right in calendar_periods(space, *membership_window(space, date_range, now, first), grain):
        waits = sorted((row["approved_at"] - row["created_at"]).total_seconds() / 3600 for row in rows
                       if row["approved_at"] and left <= row["approved_at"] < right)
        records.append({
            "period": period, "submitted": sum(left <= row["created_at"] < right for row in rows),
            "approved": len(waits),
            "activated": sum(row["state"] == "active" and row["decided_at"] and left <= row["decided_at"] < right
                             for row in rows),
            "rejected": sum(row["state"] == "revoked" and row["decided_at"] and left <= row["decided_at"] < right
                            for row in rows),
            "median_hours_to_approve": round(median(waits), 1) if waits else None,
            "p90_hours_to_approve": round(waits[min(len(waits) - 1, int(len(waits) * 0.9))], 1) if waits else None,
        })
    return ReportResult(FUNNEL_FIELDS, records if limit is None else records[:limit], {
        "grain": grain, "definition": "Join requests submitted, approved, activated and rejected per period, "
                                      "with the median and 90th-percentile wait from request to approval."})
