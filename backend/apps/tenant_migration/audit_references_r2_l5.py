"""Release-2 lane L5 audit meta ids. Money rows travel with the ledger, so their ids remap;
a pay link is dropped and machine types/sources from other domains stay provenance."""

from .audit_references_targets import AuditReference, AuditReferenceDisposition

R = AuditReferenceDisposition.REMAP
_S = AuditReference(AuditReferenceDisposition.SOURCE_LOCAL_SNAPSHOT, None, "programme_source_provenance")


def _remap(model, *pairs):
    return {pair: AuditReference(R, model) for pair in pairs}


EDGES = {
    **_remap("payments.PaymentClaim", ("payment.paid_claim_submitted", "claim_id"),
             ("payment.paid_claim_confirmed", "claim_id"), ("payment.paid_claim_rejected", "claim_id")),
    **_remap("payments.SettlementConfirmation", ("payment.settlement_awaiting_confirmation", "confirmation_id"),
             ("payment.settlement_confirmed", "confirmation_id"), ("payment.settlement_rejected", "confirmation_id")),
    **_remap("payments.ManualSettlement", ("payment.settlement_confirmed", "settlement_id")),
    **_remap("payments.PaymentCaptureFlag", ("payment.capture_flagged", "flag_id"),
             ("payment.capture_flag_resolved", "flag_id"), ("payment.document_held", "flag_id"),
             ("payment.document_released", "flag_id")),
    **_remap("payments.PaymentDocument", ("payment.document_released", "document_id")),
    **_remap("payments.PaymentDispute", ("payment.dispute_opened", "dispute_id"),
             ("payment.dispute_updated", "dispute_id")),
    **_remap("payments.Refund", ("payment.refund_pending_flagged", "refund_id")),
    **_remap("payments.OpeningBalance", ("ledger.opening_balance_set", "opening_balance_id")),
    **_remap("payments.EventFinanceBudget", ("ledger.event_budget_set", "budget_id")),
    ("payment.pay_link_created", "pay_link_id"): _S,
    ("payment.pay_link_used", "pay_link_id"): _S,
    ("ledger.expense_recorded", "machine_type_id"): _S,
    ("ledger.expense_recorded", "source_id"): _S,
    ("ledger.entry_created", "machine_type_id"): _S,
    ("ledger.entry_created", "source_id"): _S,
}
