"""Cash in hand per collector (parity O-B3).

For each person who recorded cash in this space: cash receipts they recorded, minus cash refunds they paid
out, minus cash they handed over (a `cash_handover` ledger entry whose reference is `collector:<user id>`,
see `payments.cash_handover`). What is left is the cash that should still be in their hands, per currency.

Receipts are the EFFECTIVE `ManualSettlement` rows (a corrected receipt counts once, under whoever recorded
the correction); an unconfirmed maker-checker proposal has not written a receipt yet, so it is not cash in
hand. The window's end is an "as of" date -- a balance has no start. Only core-ledger rows are read: no
rail, no module.
"""

from collections import defaultdict
from decimal import Decimal

from apps.accounts.models import User
from apps.operations.report_types import ReportResult
from apps.operations.reports_finance_sources import finance_window

FIELDS = ("collector_id", "collector", "currency", "received_cash", "refunded_cash", "handed_over", "cash_in_hand")
ZERO = Decimal("0.00")


def _collectors(space, end, actor=None):
    from apps.payments.unit_payer_scope import payer_user_ids
    from apps.payments.cash_handover import REFERENCE_PREFIX, SOURCE_KIND
    from apps.payments.models import ManualSettlement, Refund
    from apps.payments.models_ledger_entries import LedgerEntry

    table = defaultdict(lambda: {"received_cash": ZERO, "refunded_cash": ZERO, "handed_over": ZERO})
    # parity O-B3: a unit-scoped actor sees only their OWN cash, and only on their own members' charges
    payers = payer_user_ids(actor, space.pk, "view_finance")
    receipts = ManualSettlement.objects.filter(payment__makerspace=space, method="cash", amended_by__isnull=True)
    if payers is not None:
        receipts = receipts.filter(payment__member_id__in=payers, recorded_by_id=actor.pk)
    if end is not None:
        receipts = receipts.filter(received_at__lt=end)
    for user_id, currency, amount in receipts.values_list("recorded_by_id", "currency", "amount"):
        table[(user_id, currency)]["received_cash"] += amount
    refunds = Refund.objects.filter(payment__makerspace=space, provider="manual", method="cash",
                                    status="succeeded", amended_by__isnull=True)
    if payers is not None:
        refunds = refunds.filter(payment__member_id__in=payers, created_by_id=actor.pk)
    if end is not None:
        refunds = refunds.filter(refunded_at__lt=end)
    for user_id, currency, amount in refunds.values_list("created_by_id", "currency", "amount"):
        table[(user_id, currency)]["refunded_cash"] += amount
    handovers = LedgerEntry.objects.filter(makerspace=space, source_kind=SOURCE_KIND, voided_at__isnull=True,
                                           reference__startswith=REFERENCE_PREFIX)
    for reference, currency, amount in handovers.values_list("reference", "currency", "amount"):
        user_id = reference[len(REFERENCE_PREFIX):]
        if user_id.isdigit() and (payers is None or int(user_id) == actor.pk):
            table[(int(user_id), currency)]["handed_over"] += amount
    return table


def build_cash_in_hand(makerspace_id, *, limit=None, date_range=None, actor=None, **_ignored):
    from apps.makerspaces.models import Makerspace

    space = Makerspace.objects.get(pk=makerspace_id)
    _start, end = finance_window(space, date_range)
    table = _collectors(space, end, actor)
    names = {user.pk: user.get_username() for user in User.objects.filter(pk__in={key[0] for key in table})}
    records = []
    for (user_id, currency), values in sorted(table.items(), key=lambda item: (names.get(item[0][0], ""), item[0][1])):
        net = values["received_cash"] - values["refunded_cash"] - values["handed_over"]
        records.append({"collector_id": user_id, "collector": names.get(user_id, ""), "currency": currency,
                        **values, "cash_in_hand": net})
    return ReportResult(FIELDS, records if limit is None else records[:limit], {
        "definition": "Cash a collector recorded, less cash refunds they paid and cash they handed over, as of "
                      "the end of the window. cash_in_hand=received_cash-refunded_cash-handed_over; "
                      "negative means more was handed over than recorded.",
    })
