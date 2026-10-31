"""Finance-ledger reads scoped per area (#100) and the opening balances per financial year.

Writes of entries go through `ledger_api`; this module only scopes reads and keeps the
append-only opening-balance revisions (cash and bank, per financial year and currency).
"""

from django.db import transaction

from apps.audit import services as audit
from apps.payments.finance_scope import entry_q, finance_view
from apps.payments.models_ledger_entries import LedgerEntry, OpeningBalance
from apps.payments.tax.fy import fy_start


def scoped_entries(actor, makerspace_id, view=None):
    view = view or finance_view(actor, makerspace_id)
    return LedgerEntry.objects.filter(makerspace_id=makerspace_id).filter(entry_q(view))


def fy_for(makerspace, on_date):
    return fy_start(makerspace, on_date)


@transaction.atomic
def set_opening_balance(*, actor, makerspace, fy_start_date, currency, cash_amount, bank_amount):
    from apps.tenant_migration.gate_runtime import assert_write_allowed

    assert_write_allowed(makerspace.pk)
    start = fy_start(makerspace, fy_start_date)
    row = OpeningBalance.objects.create(makerspace=makerspace, fy_start=start, currency=currency.lower(),
                                        cash_amount=cash_amount, bank_amount=bank_amount, set_by=actor)
    audit.record(actor, "ledger.opening_balance_set", makerspace=makerspace, target=makerspace,
                 meta={"fy_start": start.isoformat(), "currency": row.currency, "opening_balance_id": row.pk})
    return row


def opening_balances(makerspace_id, fy_start_date):
    """The effective (newest) balance per currency for one financial year."""
    rows = OpeningBalance.objects.filter(makerspace_id=makerspace_id, fy_start=fy_start_date).order_by(
        "currency", "-set_at", "-pk")
    effective = {}
    for row in rows:
        effective.setdefault(row.currency, row)
    return list(effective.values())
