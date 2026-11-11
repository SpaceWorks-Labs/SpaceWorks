"""Renewal forecast: what comes due in the next 30, 60 and 90 days (parity O-B3, An6).

Looks at each member's CURRENT term (the latest one that is not cancelled). A term is forecast when it is
active, ends inside the horizon, belongs to a member in good standing who has not turned renewal off, and sits
on a plan that renews (rolling or financial-year; fixed-date and lifetime plans do not). The expected amount is
the plan's renewal price (new-term price when no renewal price is set), per currency; it is a forecast of
money due, not of money collected. The three rows are cumulative: 60 days contains the first 30.
"""

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from apps.makerspaces.models import MembershipTerm
from apps.operations.report_types import ReportResult

FIELDS = ("horizon_days", "currency", "terms_ending", "auto_renew_terms", "expected_amount")
HORIZONS = (30, 60, 90)


def _current_terms(space, actor=None):
    from apps.makerspaces.member_unit_scope import narrow_by_unit_lookup

    latest = {}
    rows = (MembershipTerm.objects.filter(membership__makerspace=space, membership__status="active",
                                          membership__renewal_cancelled_at__isnull=True)
            .exclude(status="cancelled").select_related("plan").order_by("membership_id", "-ends_at", "-pk"))
    # parity O-B3: a unit-scoped actor forecasts their own subtree only (counts and sums, never names)
    rows = narrow_by_unit_lookup(rows, actor, space.pk, "membership__unit_assignment__unit__path", "manage_members")
    for term in rows:
        latest.setdefault(term.membership_id, term)
    return [term for term in latest.values() if term.status == "active" and not term.is_lifetime
            and term.plan.renews]


def build_renewal_forecast(makerspace_id, *, limit=None, date_range=None, now=None, actor=None, **_ignored):
    from apps.makerspaces.models import Makerspace

    now, space = now or timezone.now(), Makerspace.objects.get(pk=makerspace_id)
    terms = _current_terms(space, actor)
    records = []
    for horizon in HORIZONS:
        due = [term for term in terms if now < term.ends_at <= now + timedelta(days=horizon)]
        by_currency = {}
        for term in due:
            by_currency.setdefault((term.plan.currency or "").lower(), []).append(term)
        for currency, rows in sorted(by_currency.items()) or [("", [])]:
            records.append({"horizon_days": horizon, "currency": currency, "terms_ending": len(rows),
                            "auto_renew_terms": sum(term.plan.auto_renew for term in rows),
                            "expected_amount": sum((term.plan.renewal_price for term in rows), Decimal("0.00"))})
    return ReportResult(FIELDS, records if limit is None else records[:limit], {
        "definition": "Current terms ending within 30, 60 and 90 days (cumulative) on renewing plans, and the "
                      "renewal price they will be charged. expected_amount is due money per currency, not a "
                      "collection estimate.",
    })
