"""Stage, travel-support and payout columns whose names resemble credentials but are not."""
_STATE = "Workflow state or target-reset mode, not a bearer credential."
_TEXT = "Member-authored statement text (mapped PII where sensitive), not a credential."
_DIGEST = "Idempotency/command integrity fingerprint, never an authentication secret."
_LEASE = "Upload worker lease identity; reset on import and never grants access."

NON_CREDENTIAL = {
    **{(label, "state"): _STATE for label in (
        "event_reimbursements.BudgetReservation", "event_reimbursements.GrantAward",
        "event_reimbursements.GrantRequest", "event_reimbursements.ReimbursementClaim",
        "events.EventStageForm", "events.StageFormAsset", "events.StageFormAssignment",
        "events.StageFormResponse", "payments.EventPayeeRevision", "payments.EventPayoutObligation",
        "payments.FinanceAttachment")},
    ("payments.EventPayoutObligation", "domain_coordination_state"): _STATE,
    ("event_reimbursements.ClaimAppeal", "statement"): _TEXT,
    ("event_reimbursements.GrantRequest", "need_statement"): _TEXT,
    ("event_reimbursements.ReimbursementProgramme", "initialization_digest"): _DIGEST,
    ("payments.EventPayoutEntry", "command_digest"): _DIGEST,
    ("payments.EventPayoutObligationRevision", "command_digest"): _DIGEST,
    ("payments.FinanceRetentionPolicyRevision", "command_digest"): _DIGEST,
    ("events.StageFormAsset", "lease_token"): _LEASE,
    ("payments.FinanceAttachment", "lease_token"): _LEASE,
}
