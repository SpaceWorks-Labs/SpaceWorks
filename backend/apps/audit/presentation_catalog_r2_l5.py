"""Release-2 lane L5: tax, offline claims, maker-checker, capture flags, disputes, pay
links and the finance ledger. Entries expose ids, kinds, statuses and currencies --
never an amount a member owes, a reference, a GSTIN, a note or a person."""

from django.utils.translation import gettext_noop
from .presentation_catalog_types import P

ENTRIES = (
    P("payment.tax_settings_updated", gettext_noop("Tax settings updated"), ("fields", "mode", "via")),
    P("payment.paid_claim_submitted", gettext_noop("Offline payment claim submitted"), ("claim_id", "method", "via_pay_link")),
    P("payment.paid_claim_confirmed", gettext_noop("Offline payment claim confirmed"), ("claim_id", "awaiting_confirmation")),
    P("payment.manual_reminder_sent", gettext_noop("Payment reminder sent"), ("channel",)),  # decision 242
    P("payment.paid_claim_rejected", gettext_noop("Offline payment claim rejected"), ("claim_id",)),
    P("payment.paid_claim_superseded", gettext_noop("Offline payment claim closed: charge settled another way"),
      ("claim_id", "payment_status")),
    P("payment.settlement_superseded", gettext_noop("Offline settlement proposal closed: charge settled another way"),
      ("confirmation_id", "payment_status")),
    P("payment.settlement_awaiting_confirmation", gettext_noop("Offline settlement awaiting a second person"),
      ("confirmation_id", "method")),
    P("payment.settlement_confirmed", gettext_noop("Offline settlement confirmed by a second person"),
      ("confirmation_id", "settlement_id")),
    P("payment.settlement_rejected", gettext_noop("Offline settlement rejected by the second person"), ("confirmation_id",)),
    P("payment.capture_flagged", gettext_noop("Unexpected online payment flagged"),
      ("flag_id", "kind", "provider", "prior_status", "currency")),
    P("payment.capture_flag_resolved", gettext_noop("Unexpected online payment decided"), ("flag_id", "kind", "resolution")),
    P("payment.document_held", gettext_noop("Receipt held for a staff decision"), ("flag_id", "kind")),
    P("payment.document_released", gettext_noop("Held receipt released"), ("flag_id", "document_id")),
    P("payment.dispute_opened", gettext_noop("Payment dispute opened"), ("dispute_id", "provider", "status")),
    P("payment.dispute_updated", gettext_noop("Payment dispute updated"), ("dispute_id", "provider", "status")),
    P("payment.pay_link_created", gettext_noop("Pay link created"), ("pay_link_id", "emailed")),
    P("payment.pay_link_used", gettext_noop("Pay link opened"), ("pay_link_id",)),
    P("payment.checkout_abandoned", gettext_noop("Unpaid online checkout closed after a week"), ("provider",)),
    P("payment.refund_pending_flagged", gettext_noop("Provider refund still pending after a day"), ("refund_id", "provider")),
    P("ledger.expense_recorded", gettext_noop("Expense recorded"),
      ("domain", "machine_type_id", "category", "source_kind", "currency", "account")),
    P("ledger.entry_created", gettext_noop("Other receipt recorded"),
      ("domain", "machine_type_id", "category", "source_kind", "currency", "account")),
    P("ledger.entry_voided", gettext_noop("Ledger entry voided"), ("kind", "domain", "category", "source_kind")),
    P("ledger.opening_balance_set", gettext_noop("Opening balance set"), ("fy_start", "currency", "opening_balance_id")),
    P("ledger.event_budget_set", gettext_noop("Event budget set"), ("currency", "budget_id")),
)
