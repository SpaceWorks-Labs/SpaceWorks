"""Refunds by local month, area and reason, without cross-currency totals.

Two sources, never double-counted:
* refund cases, grouped by the month the case opened -- `count` cases, `due` what the
  policy said was owed, `refunded` what the approved refund actually returned
  (succeeded, not superseded), `declined` how many were declined;
* refunds raised outside any case (a staff refund straight from the ledger), reported
  under reason `manual` in the month the money went back.
"""

from collections import defaultdict
from decimal import Decimal

from apps.accounts import rbac
from apps.makerspaces.local_time import to_local
from apps.operations.membership_report_scope import report_queryset
from apps.operations.report_types import ReportResult
from apps.operations.reports_fg_common import scoped_spaces
from apps.operations.reports_finance_sources import finance_window, in_window
from apps.payments.availability import SUBJECT_DOMAINS
from apps.payments.models import Refund, RefundCase

FIELDS = ("month", "area", "reason_code", "currency", "count", "refunded", "due", "declined")
ZERO = Decimal("0.00")


def _effective(refund):
    return refund is not None and refund.status == Refund.Status.SUCCEEDED and not hasattr(refund, "amended_by")


def build_refunds(makerspace_id, *, limit=None, date_range=None, actor=None):
    action = rbac.Action.VIEW_FINANCE
    records = []
    for space in scoped_spaces(makerspace_id, action, actor=actor):
        window = finance_window(space, date_range)
        groups = defaultdict(lambda: {"count": 0, "refunded": ZERO, "due": ZERO, "declined": 0})

        def add(at, area, reason, currency, **values):
            key = (to_local(space, at).strftime("%Y-%m"), area, reason, currency)
            for name, value in values.items():
                groups[key][name] += value

        cases = report_queryset(RefundCase.objects.all(), space.pk, action, actor=actor,
                                field="payment__makerspace_id")
        for case in cases.select_related("payment", "refund").prefetch_related("refund__amended_by").iterator(
                chunk_size=500):
            if not in_window(case.created_at, window):
                continue
            refunded = case.refund.amount if _effective(case.refund) else ZERO
            add(case.created_at, case.area, case.reason_code, case.payment.currency, count=1, due=case.due_amount,
                refunded=refunded, declined=int(case.status == RefundCase.Status.DECLINED))
        manual = report_queryset(Refund.objects.filter(status=Refund.Status.SUCCEEDED, refund_cases__isnull=True),
                                 space.pk, action, actor=actor, field="payment__makerspace_id")
        for refund in manual.select_related("payment").prefetch_related("amended_by").iterator(chunk_size=500):
            at = refund.refunded_at or refund.settled_at
            if not _effective(refund) or not in_window(at, window):
                continue
            add(at, SUBJECT_DOMAINS.get(refund.payment.subject_type, ""), "manual", refund.currency,
                count=1, refunded=refund.amount)
        for key in sorted(groups):
            month, area, reason, currency = key
            row = dict(month=month, area=area, reason_code=reason, currency=currency, **groups[key])
            if makerspace_id is None:
                row["makerspace_id"] = space.pk
            records.append(row)
    fields = (("makerspace_id",) + FIELDS) if makerspace_id is None else FIELDS
    return ReportResult(fields, records if limit is None else records[:limit], {
        "definition": "Refund cases by the local month they opened, plus refunds raised outside a case "
                      "(reason_code=manual) by the local month the money went back.",
        "columns": "count=cases or manual refunds; due=policy amount owed; refunded=succeeded refund "
                   "actually returned; declined=declined cases.",
        "calendar": "makerspace local time",
    })
