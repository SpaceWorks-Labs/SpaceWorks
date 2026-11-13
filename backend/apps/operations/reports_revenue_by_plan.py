"""Collected revenue by membership plan, net of refunds (parity O-B3, An4).

Money actually collected on membership charges (term start, renewal, admission and the older flat dues),
per local month, plan and currency, less refunds that really went back. Read from the canonical finance rows
(`finance_sources`), so a corrected receipt or refund counts once and nothing here is projected: the
`membership-revenue` report stays the MRR projection, this one is cash collected. A charge with no plan behind
it (flat dues) lands on the blank plan. Never summed across currencies.
"""

from collections import defaultdict
from decimal import Decimal

from apps.makerspaces.local_time import to_local
from apps.operations.report_types import ReportResult
from apps.operations.reports_finance_sources import finance_sources

FIELDS = ("period", "plan_id", "plan_name", "currency", "payments", "collected", "refunded", "net")
ZERO = Decimal("0.00")


def _plan_ids(space, rows):
    """{payment_id: plan_id or None} for the membership subjects among `rows`."""
    from apps.makerspaces.models import MembershipRequest, MembershipTerm
    from apps.payments.models import Payment

    kinds = Payment.SubjectType
    subjects = dict(Payment.objects.filter(pk__in={row["payment_id"] for row in rows}).values_list("pk", "subject_id"))
    term_types = (kinds.MEMBERSHIP_TERM, kinds.MEMBERSHIP_TERM_START)
    terms = dict(MembershipTerm.objects.filter(
        pk__in={subjects.get(row["payment_id"]) for row in rows if row["subject_type"] in term_types},
        membership__makerspace=space).values_list("pk", "plan_id"))
    requests = dict(MembershipRequest.objects.filter(
        pk__in={subjects.get(row["payment_id"]) for row in rows if row["subject_type"] == kinds.MEMBERSHIP_REQUEST},
        makerspace=space).values_list("pk", "selected_plan_id"))
    plans = {}
    for row in rows:
        subject_id = subjects.get(row["payment_id"])
        plans[row["payment_id"]] = (terms.get(subject_id) if row["subject_type"] in term_types
                                    else requests.get(subject_id) if row["subject_type"] == kinds.MEMBERSHIP_REQUEST
                                    else None)
    return plans


def build_revenue_by_plan(makerspace_id, *, limit=None, date_range=None, actor=None, **_ignored):
    from apps.makerspaces.models import Makerspace, MembershipPlan
    from apps.payments.models import Payment

    space = Makerspace.objects.get(pk=makerspace_id)
    kinds = Payment.SubjectType
    membership = (kinds.MEMBERSHIP_TERM, kinds.MEMBERSHIP_TERM_START, kinds.MEMBERSHIP_REQUEST,
                  kinds.MAKERSPACE_MEMBERSHIP)
    rows = [row for _space, row in finance_sources(space.pk, date_range=date_range, actor=actor)
            if row["subject_type"] in membership and (row.get("collected_amount") or row.get("refunded_amount"))]
    from apps.payments.unit_payer_scope import payer_user_ids

    payers = payer_user_ids(actor, space.pk, "view_finance")  # parity O-B3: a unit lead's own members' money only
    if payers is not None:
        rows = [row for row in rows if row["payer_id"] in payers]
    plan_of = _plan_ids(space, rows)
    names = dict(MembershipPlan.objects.filter(makerspace=space).values_list("pk", "name"))
    groups = defaultdict(lambda: {"payments": set(), "collected": ZERO, "refunded": ZERO})
    for row in rows:
        plan_id = plan_of.get(row["payment_id"])
        group = groups[(to_local(space, row["date"]).strftime("%Y-%m"), plan_id, row["currency"])]
        group["payments"].add(row["payment_id"])
        group["collected"] += Decimal(row.get("collected_amount") or 0)
        group["refunded"] += Decimal(row.get("refunded_amount") or 0)
    records = [{"period": period, "plan_id": plan_id, "plan_name": names.get(plan_id, ""), "currency": currency,
                "payments": len(values["payments"]), "collected": values["collected"],
                "refunded": values["refunded"], "net": values["collected"] - values["refunded"]}
               for (period, plan_id, currency), values in sorted(
                   groups.items(), key=lambda item: (item[0][0], item[0][1] or 0, item[0][2]))]
    return ReportResult(FIELDS, records if limit is None else records[:limit], {
        "definition": "Money collected on membership charges per local month and plan, less refunds that went "
                      "back (a refund is placed in the month it went back). net=collected-refunded; the blank plan "
                      "holds flat dues with no plan behind them.",
    })
