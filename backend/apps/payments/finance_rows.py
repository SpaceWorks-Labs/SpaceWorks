"""Every money movement of one space as normalized rows, for the finance-ledger reports.

Four sources, each read once and never double-counted (#94):

* member charges collected (`Payment`, the effective online capture or offline receipt)
  -> `income`;
* refunds that actually went back (succeeded, not superseded) -> `refunds` (money out);
* finance-ledger entries (`LedgerEntry`, not void) -> `other_income` or `expenses`;
* event reimbursement and prize payouts (`EventPayoutEntry`, effective, not void)
  -> `payouts` (money out, events).

Each row carries its `domain` and, for machine money, its `machine_type_id`, so the
per-area visibility of #100 filters rows here rather than in each report.
"""

from dataclasses import dataclass
from decimal import Decimal

from apps.payments.finance_scope import PAYMENT_DOMAINS

COLUMNS = ("income", "refunds", "other_income", "expenses", "payouts")
MONEY_IN = ("income", "other_income")
ONLINE = ("stripe", "razorpay")


@dataclass(frozen=True)
class MoneyRow:
    at: object
    column: str
    domain: str
    currency: str
    amount: Decimal
    machine_type_id: int | None = None
    event_id: int | None = None
    category: str = ""
    account: str = "bank"
    provider: str = ""
    method: str = ""
    subject_type: str = ""
    row_id: str = ""


def _machine_types(payment_subjects):
    """Machine type id per machine-service request id (assigned machine, bucket, then queue)."""
    if not payment_subjects:
        return {}
    from apps.machines.models import MachineServiceRequest

    rows = MachineServiceRequest.objects.filter(pk__in=payment_subjects).values_list(
        "pk", "assigned_machine__machine_type_id", "bucket__machine__machine_type_id", "queue__machine_type_id")
    return {pk: next((value for value in types if value), None) for pk, *types in rows}


def _event_ids(registration_ids):
    if not registration_ids:
        return {}
    from apps.events.models import EventRegistration

    return dict(EventRegistration.objects.filter(pk__in=registration_ids).values_list("pk", "event_id"))


def _account(method):
    return "cash" if method == "cash" else "bank"


def money_rows(space, date_range=None):
    """Yield `MoneyRow`s for one space inside `date_range` (the report window)."""
    from apps.operations.reports_finance_sources import finance_sources

    collected, refunded = [], []
    for _space, row in finance_sources(space.pk, date_range=date_range):
        if row.get("collected_amount"):
            collected.append(row)
        elif row.get("refunded_amount"):
            refunded.append(row)
    subjects = {row["payment_id"]: row for row in collected + refunded}
    from apps.payments.models import Payment

    payments = {pk: (subject_type, subject_id) for pk, subject_type, subject_id in Payment.objects.filter(
        pk__in=subjects).values_list("pk", "subject_type", "subject_id")}
    machine = _machine_types([sid for kind, sid in payments.values() if kind == "machine_service_request"])
    events = _event_ids([sid for kind, sid in payments.values() if kind == "event_registration"])
    from apps.events.orders_finance import subject_event_ids  # lane L6: orders and venue fees
    event_money = subject_event_ids(payments.values())
    for row, column, amount_key in [*((r, "income", "collected_amount") for r in collected),
                                    *((r, "refunds", "refunded_amount") for r in refunded)]:
        subject_type, subject_id = payments.get(row["payment_id"], (row["subject_type"], None))
        method = row.get("method", "") or ""
        yield MoneyRow(
            at=row["date"], column=column, domain=PAYMENT_DOMAINS.get(subject_type, "general"),
            currency=row["currency"], amount=Decimal(row[amount_key]),
            machine_type_id=machine.get(subject_id) if subject_type == "machine_service_request" else None,
            event_id=(events.get(subject_id) if subject_type == "event_registration"
                      else event_money.get((subject_type, subject_id))),
            category=subject_type, account=_account(method),
            provider=method if row["row_kind"] in ("online_settlement", "refund") and method in ONLINE else "",
            method=method, subject_type=subject_type, row_id=f"{row['row_kind']}:{row['row_id']}")
    yield from _ledger_rows(space, date_range)
    yield from _payout_rows(space, date_range)


def _ledger_rows(space, date_range):
    from apps.makerspaces.local_time import local_day_bounds
    from apps.operations.reports_finance_sources import finance_window, in_window
    from apps.payments.models_ledger_entries import LedgerEntry

    bounds = finance_window(space, date_range)
    for entry in LedgerEntry.objects.filter(makerspace=space, voided_at__isnull=True).iterator(chunk_size=1000):
        at = local_day_bounds(space, entry.entry_date)[0]
        if not in_window(at, bounds):
            continue
        yield MoneyRow(at=at, column="other_income" if entry.kind == "receipt" else "expenses",
                       domain=entry.domain, currency=entry.currency, amount=entry.amount,
                       machine_type_id=entry.machine_type_id, event_id=entry.event_id, category=entry.category,
                       account=entry.account, method=entry.method, row_id=f"ledger:{entry.pk}")


def _payout_rows(space, date_range):
    from apps.operations.reports_finance_sources import finance_window, in_window
    from apps.payments.event_payouts.payout_models import EventPayoutEntry
    from apps.payments.money import minor_unit_exponent

    bounds = finance_window(space, date_range)
    rows = EventPayoutEntry.objects.filter(obligation__makerspace=space, is_void=False, amended_by__isnull=True)
    for entry in rows.select_related("obligation").iterator(chunk_size=1000):
        if not in_window(entry.paid_at, bounds):
            continue
        amount = Decimal(entry.amount_minor).scaleb(-minor_unit_exponent(entry.currency))
        yield MoneyRow(at=entry.paid_at, column="payouts", domain="events", currency=entry.currency.lower(),
                       amount=amount, event_id=entry.obligation.event_id, category="reimbursement",
                       account=_account(entry.method), method=entry.method, row_id=f"payout:{entry.pk}")
