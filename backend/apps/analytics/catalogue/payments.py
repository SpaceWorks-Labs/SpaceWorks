"""Analytics views: the payments ledger, AMOUNTS ONLY (#163B).

No payer, provider order/payment/session ids, checkout URLs, connected accounts, tax or
pricing snapshots, labels, descriptions, counterparties, references or receipt evidence:
money is what was owed or moved, in which domain, when and in what state.
"""

from .types import Col, View

D = "payments"
VIEWS = (
    View("payments", D, "Charges and payments: amount, currency, subject kind and state.",
         "FROM {payments.Payment} p", "p.makerspace_id", (
             Col("payment_id", "p.id", "Charge id."),
             Col("subject_type", "p.subject_type", "What it pays for (loan, booking, event, membership...)."),
             Col("amount", "p.amount", "Amount."),
             Col("currency", "p.currency", "Currency."),
             Col("status", "p.status", "Charge state."),
             Col("provider", "p.provider", "Offline, unclaimed or the online provider."),
             Col("online_rail", "p.online_rail", "Hosted checkout or native sheet."),
             Col("due_at", "p.due_at", "Due."),
             Col("created_at", "p.created_at", "Raised."),
             Col("updated_at", "p.updated_at", "Last changed."),
         )),
    View("finance_ledger", D, "Money in and out from the finance ledger (L5), by domain and category.",
         "FROM {payments.LedgerEntry} e", "e.makerspace_id", (
             Col("entry_id", "e.id", "Entry id."),
             Col("kind", "e.kind", "Income or expense."),
             Col("domain", "e.domain", "Area it belongs to."),
             Col("machine_type_id", "e.machine_type_id", "Machine type, for machine money (machine_types)."),
             Col("event_id", "e.event_id", "Event, for event money (events)."),
             Col("category", "e.category", "Category."),
             Col("method", "e.method", "Cash, bank, card and so on."),
             Col("account", "e.account", "Cash or bank account."),
             Col("amount", "e.amount", "Amount."),
             Col("currency", "e.currency", "Currency."),
             Col("entry_date", "e.entry_date", "Date of the movement."),
             Col("source_kind", "e.source_kind", "What recorded it."),
             Col("is_void", "e.voided_at IS NOT NULL", "Voided entry."),
             Col("created_at", "e.created_at", "Recorded."),
         )),
    View("refund_cases", D, "Refund cases (staff-approved; nothing is refunded automatically).",
         "FROM {payments.RefundCase} c JOIN {payments.Payment} p ON p.id = c.payment_id", "p.makerspace_id", (
             Col("refund_case_id", "c.id", "Case id."),
             Col("payment_id", "c.payment_id", "Charge (payments)."),
             Col("kind", "c.kind", "Case kind."),
             Col("area", "c.area", "Area."),
             Col("reason_code", "c.reason_code", "Reason code."),
             Col("status", "c.status", "Case state."),
             Col("due_amount", "c.due_amount", "Amount the policy says is due."),
             Col("approved_amount", "c.approved_amount", "Amount staff approved."),
             Col("created_at", "c.created_at", "Opened."),
             Col("decided_at", "c.decided_at", "Decided."),
         )),
)
