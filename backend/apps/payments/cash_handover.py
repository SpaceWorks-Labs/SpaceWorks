"""A collector handing cash to the treasurer or the bank (parity O-B3).

The `cash-in-hand` report is what each collector received in cash minus what they handed over. A hand-over is
recorded as a finance-ledger entry with `source_kind="cash_handover"` and `reference="collector:<user id>"`.
It is a TRANSFER, not spending: the income/spending reports and the platform overview leave it out, while the
ledger list still shows it (and it can be voided like any entry, with a reason).
"""

from apps.accounts import rbac
from apps.audit import services as audit
from apps.makerspaces.models import Makerspace
from apps.payments import ledger_api
from apps.payments.models_ledger_entries import LedgerEntry

SOURCE_KIND = "cash_handover"
REFERENCE_PREFIX = "collector:"


def collector_reference(user_id):
    return f"{REFERENCE_PREFIX}{user_id}"


def record_cash_handover(*, actor, space, collector, amount, currency, entry_date=None, note=""):
    """The collector must still hold record_payment here, so a hand-over always names a real collector."""
    if not rbac.scope_by_action(collector, rbac.Action.RECORD_PAYMENT, Makerspace.objects.filter(pk=space.pk),
                                field="pk").exists():
        raise ledger_api.LedgerConflict("That person does not collect payments in this space.", "collector_invalid")
    entry = ledger_api.record_expense(
        space, LedgerEntry.Domain.GENERAL, None, amount, currency, LedgerEntry.Method.CASH,
        collector_reference(collector.pk), None, SOURCE_KIND, "", actor, category=SOURCE_KIND,
        description=(note or "Cash handed over")[:300], entry_date=entry_date)
    audit.record(actor, "payment.cash_handover_recorded", makerspace=space, target=entry,
                 meta={"collector_id": collector.pk, "currency": entry.currency})
    return entry
