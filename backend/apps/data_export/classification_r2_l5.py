"""Release-2 lane L5 (money, tax and the finance ledger): literal export classification.

Every L5 money row is the space's own financial record and exports with the space:
tax policy (a GSTIN is business data), per-FY document counters, finance-ledger entries,
opening balances, event budgets, payers' offline claims (a UTR is a payment reference,
never contact data), maker-checker confirmations, capture flags and disputes.

`PaymentPayLink` is omitted: its digest names a bearer capability for one charge, and a
link is reissued on the target if still needed. New columns: `Payment.tax_snapshot` and
`method_label` (a masked provider label, never card data), `PaymentDocument.number_series`
and `fy_start`, and the billing policy's UPI ID and payee name.
"""

from .types import TenantPredicate as P

EXPORTED_FIELDS = {
    "payments.MakerspaceTaxSettings": "id makerspace mode tax_name rate_bps prices_include_tax gstin state_code "
                                      "scheme exempt sac_code foreign_currency lut_number invoice_prefix "
                                      "credit_note_prefix updated_by updated_at",
    "payments.DocumentNumberCounter": "id makerspace series fy_start next_number",
    "payments.LedgerEntry": "id makerspace kind domain machine_type machine_type_label event category method account "
                            "amount currency entry_date description counterparty reference source_kind source_id "
                            "receipt created_by created_at voided_at voided_by void_reason",
    "payments.OpeningBalance": "id makerspace fy_start currency cash_amount bank_amount set_by set_at",
    "payments.EventFinanceBudget": "id makerspace event event_id_snapshot currency amount set_by set_at",
    "payments.PaymentClaim": "id makerspace payment claimant pay_link method reference paid_on amount currency status "
                             "decided_by decided_at decision_note created_at",
    "payments.SettlementConfirmation": "id payment method reference received_at amount currency proposed_by claim "
                                       "status decided_by decided_at decision_note settlement created_at",
    "payments.PaymentCaptureFlag": "id makerspace payment kind provider provider_payment_id provider_event_id "
                                   "captured_minor captured_currency captured_amount prior_status flagged_at "
                                   "resolution resolution_note resolved_by resolved_at refund_case",
    "payments.PaymentDispute": "id makerspace payment provider provider_dispute_id amount currency reason status "
                               "provider_status evidence_due_at opened_at updated_at",
    "payments.PaymentDisputeEvent": "id dispute status provider_status provider_event_id amount recorded_at",
}
EXTRA_FIELDS = {
    "payments.Payment": "tax_snapshot method_label",
    "payments.PaymentDocument": "number_series fy_start",
    "payments.MakerspaceBillingSettings": "upi_vpa upi_payee_name",
}
OMITTED_MODELS = {
    "payments.PaymentPayLink": "Bearer pay-link capability (digest only); staff issue a new link on the target.",
}
DATASET_SPECS = {
    "payments.MakerspaceTaxSettings": ("makerspace/tax_settings.csv", P(("makerspace",))),
    "payments.DocumentNumberCounter": ("payments/document_counters.csv", P(("makerspace",))),
    "payments.LedgerEntry": ("payments/ledger_entries.csv", P(("makerspace",))),
    "payments.OpeningBalance": ("payments/opening_balances.csv", P(("makerspace",))),
    "payments.EventFinanceBudget": ("payments/event_budgets.csv", P(("makerspace",))),
    "payments.PaymentClaim": ("payments/paid_claims.csv", P(("makerspace",))),
    "payments.SettlementConfirmation": ("payments/settlement_confirmations.csv", P(("payment__makerspace",))),
    "payments.PaymentCaptureFlag": ("payments/capture_flags.csv", P(("makerspace",))),
    "payments.PaymentDispute": ("payments/disputes.csv", P(("makerspace",))),
    "payments.PaymentDisputeEvent": ("payments/dispute_events.csv", P(("dispute__makerspace",))),
}
RELATIONAL_USER_FIELDS = frozenset({
    ("payments.MakerspaceTaxSettings", "updated_by"),
    ("payments.LedgerEntry", "created_by"),
    ("payments.LedgerEntry", "voided_by"),
    ("payments.OpeningBalance", "set_by"),
    ("payments.EventFinanceBudget", "set_by"),
    ("payments.PaymentClaim", "claimant"),
    ("payments.PaymentClaim", "decided_by"),
    ("payments.SettlementConfirmation", "proposed_by"),
    ("payments.SettlementConfirmation", "decided_by"),
    ("payments.PaymentCaptureFlag", "resolved_by"),
    ("payments.PaymentPayLink", "created_by"),
})
# The credential-name guard matches `*code`; a GST state code is a public place-of-supply
# code, not a secret.
NON_CREDENTIAL = {
    ("payments.MakerspaceTaxSettings", "state_code"): "GST state code (place of supply), not a credential.",
}
# Frozen tax policy figures, rates and GSTINs; no account or object references.
JSON_FIELDS = frozenset({("payments.Payment", "tax_snapshot")})


def extend(fields):
    fields.update(EXPORTED_FIELDS)
    for label, extra in EXTRA_FIELDS.items():
        fields[label] += " " + extra
    return fields
