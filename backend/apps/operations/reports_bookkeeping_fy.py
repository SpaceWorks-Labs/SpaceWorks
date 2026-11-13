"""Bookkeeping by financial year (X22): receipts-and-payments account and subscription income.

* `receipts-payments` -- per financial year, currency and account (cash or bank): the
  opening balance staff set, money received, money paid out and the closing balance.
  Read from the same rows as income versus spending (`payments.finance_rows`).
* `subscription-income` -- membership renewal income earned day by day across the
  financial years each paid term covers, with advances (collected now, earned later) and
  arrears (earned now, collected later or still owed).

Financial years come from the space's FY start (`payments.tax.fy`).
"""

from collections import defaultdict
from decimal import Decimal

from apps.makerspaces.local_time import to_local
from apps.operations.report_types import ReportResult
from apps.payments.finance_rows import MONEY_IN, money_rows
from apps.payments.tax.fy import fy_end_exclusive, fy_name, fy_start

RP_FIELDS = ("financial_year", "currency", "account", "opening", "receipts", "payments", "closing")
SUB_FIELDS = ("financial_year", "currency", "collected", "earned", "advance", "arrears")
ZERO = Decimal("0.00")


def _spaces(makerspace_id):
    from apps.makerspaces.models import Makerspace
    from apps.operations.report_scope import scoped_ids

    return Makerspace.objects.filter(pk__in=scoped_ids(makerspace_id)).order_by("pk")


def build_receipts_payments(makerspace_id, *, limit=None, date_range=None, actor=None):
    from apps.payments.ledger_entries import opening_balances

    records = []
    for space in _spaces(makerspace_id):
        groups = defaultdict(lambda: {"receipts": ZERO, "payments": ZERO})
        for row in money_rows(space, date_range):
            start = fy_start(space, to_local(space, row.at).date())
            side = "receipts" if row.column in MONEY_IN else "payments"
            groups[(start, row.currency, row.account)][side] += row.amount
        openings = {}
        for start in {key[0] for key in groups}:
            for balance in opening_balances(space.pk, start):
                openings[(start, balance.currency, "cash")] = balance.cash_amount
                openings[(start, balance.currency, "bank")] = balance.bank_amount
                groups.setdefault((start, balance.currency, "cash"), {"receipts": ZERO, "payments": ZERO})
                groups.setdefault((start, balance.currency, "bank"), {"receipts": ZERO, "payments": ZERO})
        for key in sorted(groups):
            start, currency, account = key
            opening = openings.get(key, ZERO)
            values = groups[key]
            records.append({"financial_year": fy_name(start), "currency": currency, "account": account,
                            "opening": opening, **values,
                            "closing": opening + values["receipts"] - values["payments"]})
    return ReportResult(RP_FIELDS, records if limit is None else records[:limit], {
        "definition": "Receipts and payments account per financial year: opening balance (as set by "
                      "finance staff), every receipt and payment in the window, and the closing balance.",
        "columns": "cash = cash method; bank = every other method, online captures included.",
    })


def _collected_at(payment, settlements, documents):
    if payment.status == "paid_offline":
        settlement = settlements.get(payment.pk)
        return settlement.received_at if settlement else payment.updated_at
    if payment.status == "paid_online":
        document = documents.get(payment.pk)
        return document.money_at if document else payment.updated_at
    return None


def _split_by_fy(space, amount, currency, starts_at, ends_at):
    """{fy_start: earned}: `amount` spread over the term's local days, exact to the unit."""
    from apps.payments.tax.engine import largest_remainder

    first, last = to_local(space, starts_at).date(), to_local(space, ends_at).date()
    if last <= first:
        return {fy_start(space, first): amount}
    days, cursor = {}, first
    while cursor < last:
        start = fy_start(space, cursor)
        stop = min(fy_end_exclusive(start), last)
        days[start] = (stop - cursor).days
        cursor = stop
    keys = sorted(days)
    return dict(zip(keys, largest_remainder(amount, [days[key] for key in keys], currency)))


def build_subscription_income(makerspace_id, *, limit=None, date_range=None, actor=None):
    from apps.makerspaces.models_membership_plans import MembershipTerm
    from apps.payments.models import ManualSettlement, Payment, PaymentDocument

    records = []
    for space in _spaces(makerspace_id):
        payments = list(Payment.objects.filter(makerspace=space, subject_type="membership_term").exclude(
            status__in=("waived", "canceled")))
        terms = {term.pk: term for term in MembershipTerm.objects.filter(pk__in=[p.subject_id for p in payments])}
        settlements = ManualSettlement.effective_for_many(payments)
        documents = {doc.payment_id: doc for doc in PaymentDocument.objects.filter(
            payment__in=payments, kind="receipt", settlement__isnull=True, refund__isnull=True,
            reverses__isnull=True)}
        groups = defaultdict(lambda: dict.fromkeys(SUB_FIELDS[2:], ZERO))
        for payment in payments:
            term = terms.get(payment.subject_id)
            if term is None:
                continue
            collected_at = _collected_at(payment, settlements, documents)
            paid_fy = fy_start(space, to_local(space, collected_at).date()) if collected_at else None
            if paid_fy is not None:
                groups[(paid_fy, payment.currency)]["collected"] += payment.amount
            for start, earned in _split_by_fy(space, payment.amount, payment.currency, term.starts_at, term.ends_at).items():
                group = groups[(start, payment.currency)]
                group["earned"] += earned
                if paid_fy is None or paid_fy > start:
                    group["arrears"] += earned
                elif paid_fy < start:
                    groups[(paid_fy, payment.currency)]["advance"] += earned
        for (start, currency), values in sorted(groups.items()):
            records.append({"financial_year": fy_name(start), "currency": currency, **values})
    return ReportResult(SUB_FIELDS, records if limit is None else records[:limit], {
        "definition": "Membership renewal charges earned evenly by local day across the financial years "
                      "their term covers.",
        "columns": "collected=received in the year; earned=the year's share of paid or owed terms; "
                   "advance=received in the year for later years; arrears=earned in the year but received "
                   "later or still owed.",
    })
