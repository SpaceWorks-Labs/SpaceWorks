"""Membership insights built from terms (G19, X34): renewals and the membership bridge.

Behind `membership.insights`, tenant-local (`makerspace_id` is always given; the view has
already checked the reader's action). Periods follow the space's local calendar
(`calendar_periods`), and FY presets come from the financial-year endpoint.

Coverage: a membership is in good standing while one of its non-cancelled terms covers
the instant; gaps no longer than the earlier term's renewal grace are bridged (a late
renewal is not a lapse). A cancelled term covers until its recorded cancellation. Each
coverage stretch ends either REVOKED (the membership was revoked then) or LAPSED. The
bridge is therefore exact by construction: start + joined + came back - lapsed - revoked
= end.
"""
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from apps.makerspaces.models import MakerspaceMembership, MembershipTerm, MembershipTermStatusEvent
from apps.operations.report_types import ReportResult
from apps.operations.reports_fg_common import calendar_periods, membership_window

PAID = ("paid_online", "paid_offline")
_EPS = timedelta(microseconds=1)


def _terms(space):
    return (MembershipTerm.objects.filter(membership__makerspace=space)
            .select_related("plan", "renewal_payment").order_by("membership_id", "starts_at", "pk"))


def coverage(space, now):
    """`{membership_id: [(start, end_or_None, "revoked"|"lapsed"|None, first)]}`."""
    cancelled_at = dict(MembershipTermStatusEvent.objects.filter(
        makerspace=space, status="cancelled").values_list("term_id", "effective_at"))
    revoked = dict(MakerspaceMembership.objects.filter(makerspace=space, revoked_at__isnull=False)
                   .values_list("pk", "revoked_at"))
    spans = {}
    for term in _terms(space):
        end = term.ends_at
        if term.status == "cancelled":
            end = min(end, cancelled_at.get(term.pk, term.starts_at))
        if end <= term.starts_at or term.starts_at > now:
            continue
        spans.setdefault(term.membership_id, []).append(
            (term.starts_at, end, timedelta(days=term.plan.renewal_grace_days or 0)))
    result = {}
    for membership_id, rows in spans.items():
        merged = []
        for start, end, grace in sorted(rows):
            if merged and start <= merged[-1][1] + merged[-1][2]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end), grace)
            else:
                merged.append((start, end, grace))
        out, revoked_at = [], revoked.get(membership_id)
        for index, (start, end, grace) in enumerate(merged):
            kind = None
            if revoked_at is not None and start <= revoked_at <= end + timedelta(days=1):
                end, kind = min(end, revoked_at), "revoked"
            elif end + grace <= now:
                # Lapsed once its grace ran out; still in grace counts as standing.
                kind = "lapsed"
            out.append((start, None if kind is None else end, kind, index == 0))
        result[membership_id] = out
    return result


def _covers(span, instant):
    start, end, _kind, _first = span
    return start <= instant and (end is None or instant < end)


BRIDGE_FIELDS = ("period", "start", "joined", "came_back", "lapsed", "revoked", "end")


def build_membership_bridge(makerspace_id, *, limit=None, date_range=None, grain="month", now=None, actor=None):
    from apps.makerspaces.models import Makerspace
    now = now or timezone.now()
    space = Makerspace.objects.get(pk=makerspace_id)
    spans = [span for rows in coverage(space, now).values() for span in rows]
    first = min((span[0] for span in spans), default=now)
    records = []
    window_start, window_end = membership_window(space, date_range, now, first)
    for period, left, right in calendar_periods(space, window_start, window_end, grain):
        def within(at):
            return at is not None and left <= at < right
        records.append({
            "period": period,
            "start": sum(_covers(span, left - _EPS) for span in spans),
            "joined": sum(within(span[0]) and span[3] for span in spans),
            "came_back": sum(within(span[0]) and not span[3] for span in spans),
            "lapsed": sum(span[2] == "lapsed" and within(span[1]) for span in spans),
            "revoked": sum(span[2] == "revoked" and within(span[1]) for span in spans),
            "end": sum(_covers(span, right - _EPS) for span in spans),
        })
    return ReportResult(BRIDGE_FIELDS, records if limit is None else records[:limit], {
        "grain": grain,
        "definition": "Members in good standing at each period start and end, and what moved them: "
                      "first joins, returns after a gap, lapses and revocations. start + joined + came_back "
                      "- lapsed - revoked = end.",
        "limitations": "Gaps shorter than a plan's renewal grace count as continuous membership.",
    })


RENEWAL_FIELDS = ("period", "currency", "due", "renewed", "renewal_rate", "first_year_due", "first_year_renewed",
                  "first_year_renewal_rate", "forecast_amount", "actual_amount", "charges_raised",
                  "charges_collected", "collection_rate")


def _rate(part, whole):
    return None if not whole else (Decimal(part) * 100 / Decimal(whole)).quantize(Decimal("0.01"))


def build_membership_renewals(makerspace_id, *, limit=None, date_range=None, grain="month", now=None, actor=None):
    from apps.makerspaces.models import Makerspace
    now = now or timezone.now()
    space = Makerspace.objects.get(pk=makerspace_id)
    terms = [term for term in _terms(space) if term.status != "cancelled" and not term.is_lifetime and term.plan.renews]
    starts = {}
    for term in _terms(space).exclude(status="cancelled"):
        starts.setdefault(term.membership_id, []).append((term.starts_at, term.renewed_from_id))

    def renewed(term):
        grace = timedelta(days=term.plan.renewal_grace_days or 0)
        return any(from_id == term.pk or term.ends_at - timedelta(days=1) <= at <= term.ends_at + grace
                   for at, from_id in starts.get(term.membership_id, ()) if at != term.starts_at)

    first = min((term.ends_at for term in terms), default=now)
    window_start, window_end = membership_window(space, date_range, max(now, first), first)
    records = []
    for period, left, right in calendar_periods(space, window_start, window_end, grain):
        groups = {}
        for term in terms:
            if left <= term.ends_at < right:
                groups.setdefault(term.currency or term.plan.currency, []).append(term)
        for currency, due in sorted(groups.items()):
            done = [term for term in due if renewed(term)]
            new_due = [term for term in due if term.kind == "new"]
            new_done = [term for term in new_due if term in done]
            raised = [term.renewal_payment for term in due if term.renewal_payment_id]
            collected = [payment for payment in raised if payment.status in PAID]
            records.append({
                "period": period, "currency": currency, "due": len(due), "renewed": len(done),
                "renewal_rate": _rate(len(done), len(due)), "first_year_due": len(new_due),
                "first_year_renewed": len(new_done), "first_year_renewal_rate": _rate(len(new_done), len(new_due)),
                "forecast_amount": sum((term.plan.renewal_price for term in due), Decimal("0.00")),
                "actual_amount": sum((payment.amount for payment in collected), Decimal("0.00")),
                "charges_raised": len(raised), "charges_collected": len(collected),
                "collection_rate": _rate(len(collected), len(raised)),
            })
    return ReportResult(RENEWAL_FIELDS, records if limit is None else records[:limit], {
        "grain": grain,
        "definition": "Terms ending in each period, how many renewed (a next term within grace), first-year "
                      "renewals, the renewal amount forecast from plan prices against what was collected, "
                      "and the share of renewal charges collected.",
        "limitations": "Forecast uses today's plan renewal price; lifetime and non-renewing plans are excluded.",
    })
