"""Lane L5 rows in the capture-bound money fingerprint.

Anything that can still move or explain money after a capture participates: open
"I've paid" claims and settlements awaiting a second person (either can settle a captured
debt), open capture flags (a held receipt can be released), dispute status, finance-ledger
entries (an expense recorded or voided after the freeze), opening balances, event budgets
and the per-FY document counters. Each key is omitted when empty, so a capture taken by a
space that uses none of this keeps its existing fingerprint.
"""


def _rows(model, using, values, **lookup):
    return [{key: str(value) for key, value in row.items()}
            for row in model.objects.using(using).filter(**lookup).order_by("pk").values(*values)]


def l5_money_rows(makerspace_id, using="default"):
    from django.apps import apps

    get = apps.get_model
    parts = {
        "paid_claims": _rows(get("payments.PaymentClaim"), using,
                             ("id", "payment_id", "status", "reference", "amount", "decided_at"),
                             makerspace_id=makerspace_id),
        "settlement_confirmations": _rows(get("payments.SettlementConfirmation"), using,
                                          ("id", "payment_id", "status", "amount", "settlement_id"),
                                          payment__makerspace_id=makerspace_id),
        "capture_flags": _rows(get("payments.PaymentCaptureFlag"), using,
                               ("id", "payment_id", "kind", "resolution", "captured_amount"),
                               makerspace_id=makerspace_id),
        "disputes": _rows(get("payments.PaymentDispute"), using, ("id", "payment_id", "status", "amount"),
                          makerspace_id=makerspace_id),
        "ledger_entries": _rows(get("payments.LedgerEntry"), using,
                                ("id", "kind", "domain", "amount", "currency", "entry_date", "voided_at"),
                                makerspace_id=makerspace_id),
        "opening_balances": _rows(get("payments.OpeningBalance"), using,
                                  ("id", "fy_start", "currency", "cash_amount", "bank_amount"),
                                  makerspace_id=makerspace_id),
        "event_budgets": _rows(get("payments.EventFinanceBudget"), using, ("id", "currency", "amount"),
                               makerspace_id=makerspace_id),
        "fy_counters": _rows(get("payments.DocumentNumberCounter"), using, ("series", "fy_start", "next_number"),
                             makerspace_id=makerspace_id),
    }
    return {key: rows for key, rows in parts.items() if rows}
