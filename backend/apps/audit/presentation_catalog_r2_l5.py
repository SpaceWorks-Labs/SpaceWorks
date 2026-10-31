"""Release-2 lane L5: tax, offline claims, maker-checker, capture flags, disputes, pay
links and the finance ledger. Entries expose ids, kinds, statuses and currencies --
never an amount a member owes, a reference, a GSTIN, a note or a person."""

from .presentation_catalog_types import P

ENTRIES = (
    P("payment.tax_settings_updated", "Tax settings updated", ("fields", "mode", "via")),
    P("payment.paid_claim_submitted", "Offline payment claim submitted", ("claim_id", "method", "via_pay_link")),
    P("payment.paid_claim_confirmed", "Offline payment claim confirmed", ("claim_id", "awaiting_confirmation")),
    P("payment.paid_claim_rejected", "Offline payment claim rejected", ("claim_id",)),
    P("payment.settlement_awaiting_confirmation", "Offline settlement awaiting a second person",
      ("confirmation_id", "method")),
    P("payment.settlement_confirmed", "Offline settlement confirmed by a second person",
      ("confirmation_id", "settlement_id")),
    P("payment.settlement_rejected", "Offline settlement rejected by the second person", ("confirmation_id",)),
    P("payment.capture_flagged", "Unexpected online payment flagged",
      ("flag_id", "kind", "provider", "prior_status", "currency")),
    P("payment.capture_flag_resolved", "Unexpected online payment decided", ("flag_id", "kind", "resolution")),
    P("payment.document_held", "Receipt held for a staff decision", ("flag_id", "kind")),
    P("payment.document_released", "Held receipt released", ("flag_id", "document_id")),
    P("payment.dispute_opened", "Payment dispute opened", ("dispute_id", "provider", "status")),
    P("payment.dispute_updated", "Payment dispute updated", ("dispute_id", "provider", "status")),
    P("payment.pay_link_created", "Pay link created", ("pay_link_id", "emailed")),
    P("payment.pay_link_used", "Pay link opened", ("pay_link_id",)),
    P("payment.checkout_abandoned", "Unpaid online checkout closed after a week", ("provider",)),
    P("payment.refund_pending_flagged", "Provider refund still pending after a day", ("refund_id", "provider")),
    P("ledger.expense_recorded", "Expense recorded",
      ("domain", "machine_type_id", "category", "source_kind", "currency", "account")),
    P("ledger.entry_created", "Other receipt recorded",
      ("domain", "machine_type_id", "category", "source_kind", "currency", "account")),
    P("ledger.entry_voided", "Ledger entry voided", ("kind", "domain", "category", "source_kind")),
    P("ledger.opening_balance_set", "Opening balance set", ("fy_start", "currency", "opening_balance_id")),
    P("ledger.event_budget_set", "Event budget set", ("currency", "budget_id")),
)
