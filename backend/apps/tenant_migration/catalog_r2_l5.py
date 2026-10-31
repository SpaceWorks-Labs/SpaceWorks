"""Release-2 lane L5 (money, tax, finance ledger): tenant-dump field snapshot and authority.

Every L5 money row travels with the ledger it explains (data_export
`classification_r2_l5`), except `PaymentPayLink`, a bearer capability that is DROPPED
(a claim made through one keeps its row; its link reference is cleared). Provider handles
on capture flags and disputes are the provider's own identifiers of money already moved;
they stay readable as history and cannot authorize anything on the target, where the
rail's credentials are re-entered. A charge's `tax_snapshot` is frozen history and
travels unchanged; the masked `method_label` likewise.
"""

FIELD_NAMES = {
    "payments.MakerspaceTaxSettings": frozenset(
        "id makerspace mode tax_name rate_bps prices_include_tax gstin state_code scheme exempt sac_code "
        "foreign_currency lut_number invoice_prefix credit_note_prefix updated_by updated_at".split()),
    "payments.DocumentNumberCounter": frozenset("id makerspace series fy_start next_number".split()),
    "payments.LedgerEntry": frozenset(
        "id makerspace kind domain machine_type machine_type_label event category method account amount currency "
        "entry_date description counterparty reference source_kind source_id receipt created_by created_at "
        "voided_at voided_by void_reason".split()),
    "payments.OpeningBalance": frozenset("id makerspace fy_start currency cash_amount bank_amount set_by set_at".split()),
    "payments.EventFinanceBudget": frozenset(
        "id makerspace event event_id_snapshot currency amount set_by set_at".split()),
    "payments.PaymentClaim": frozenset(
        "id makerspace payment claimant pay_link method reference paid_on amount currency status decided_by "
        "decided_at decision_note created_at".split()),
    "payments.SettlementConfirmation": frozenset(
        "id payment method reference received_at amount currency proposed_by claim status decided_by decided_at "
        "decision_note settlement created_at".split()),
    "payments.PaymentCaptureFlag": frozenset(
        "id makerspace payment kind provider provider_payment_id provider_event_id captured_minor captured_currency "
        "captured_amount prior_status flagged_at resolution resolution_note resolved_by resolved_at "
        "refund_case".split()),
    "payments.PaymentDispute": frozenset(
        "id makerspace payment provider provider_dispute_id amount currency reason status provider_status "
        "evidence_due_at opened_at updated_at".split()),
    "payments.PaymentDisputeEvent": frozenset(
        "id dispute status provider_status provider_event_id amount recorded_at".split()),
    "payments.PaymentPayLink": frozenset(
        "id makerspace payment token_digest expires_at created_by created_at revoked_at last_used_at".split()),
}
EXTRA_FIELDS = {
    "payments.Payment": frozenset({"tax_snapshot", "method_label"}),
    "payments.PaymentDocument": frozenset({"number_series", "fy_start"}),
    "payments.MakerspaceBillingSettings": frozenset({"upi_vpa", "upi_payee_name"}),
}
PROJECTED_LABELS = frozenset(FIELD_NAMES) - {"payments.PaymentPayLink"}


def fk_policies(policy, disposition):
    """A ledger entry's machine type resolves through the built-in/custom type map."""
    return {("payments.LedgerEntry", "machine_type"): policy(
        disposition.REMAP_RESOLVED, "Use the built-in/custom machine type map.")}


def authority_entries(authority, disposition):
    def same(label, names, chosen, reason):
        return tuple(((label, name), authority(chosen, reason)) for name in names.split())

    keep = disposition.PRESERVE
    return (
        *same("payments.Payment", "tax_snapshot method_label", keep,
              "Frozen tax policy and the masked provider label are the charge's own history."),
        *same("payments.PaymentDocument", "number_series fy_start", keep,
              "Issued document numbering is immutable legal history."),
        *same("payments.MakerspaceBillingSettings", "upi_vpa upi_payee_name", keep,
              "The space's UPI ID and payee name are its own collection details."),
        *same("payments.MakerspaceTaxSettings", "mode tax_name rate_bps prices_include_tax gstin state_code scheme "
              "exempt sac_code foreign_currency lut_number invoice_prefix credit_note_prefix updated_at", keep,
              "Tax registration and policy are the space's own business configuration."),
        *same("payments.DocumentNumberCounter", "series fy_start next_number", keep,
              "Per-FY series continue gaplessly after a move."),
        *same("payments.LedgerEntry", "kind domain machine_type_label category method account amount currency "
              "entry_date description counterparty reference source_kind source_id created_at voided_at "
              "void_reason", keep, "The finance ledger is the space's own money record."),
        *same("payments.OpeningBalance", "fy_start currency cash_amount bank_amount set_at", keep,
              "Opening balances are the space's own books."),
        *same("payments.EventFinanceBudget", "event_id_snapshot currency amount set_at", keep,
              "An event budget is the space's own planning record."),
        *same("payments.PaymentClaim", "method reference paid_on amount currency status decided_at decision_note "
              "created_at", keep, "An offline payment claim and its decision explain the cash book."),
        *same("payments.SettlementConfirmation", "method reference received_at amount currency status decided_at "
              "decision_note created_at", keep, "Maker-checker history explains how money was confirmed."),
        *same("payments.PaymentCaptureFlag", "kind provider provider_payment_id provider_event_id captured_minor "
              "captured_currency captured_amount prior_status flagged_at resolution resolution_note resolved_at",
              keep, "A flagged capture is history of money already moved; handles authorize nothing."),
        *same("payments.PaymentDispute", "provider provider_dispute_id amount currency reason status "
              "provider_status evidence_due_at opened_at updated_at", keep,
              "A dispute record is history; the provider moves disputed money itself."),
        *same("payments.PaymentDisputeEvent", "status provider_status provider_event_id amount recorded_at",
              keep, "Dispute status history is append-only record."),
    )
