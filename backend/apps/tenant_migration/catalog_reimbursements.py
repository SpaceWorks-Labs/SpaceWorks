"""Export/Lane D dispositions for stage forms, reimbursements and the core payout ledger.

None of these rows travel in a tenant export yet. Their faithful transfer needs the
custodial transforms in each package's ``portable.py`` (mandatory payee/decision
envelopes, typed UUID/JSON remaps, paused imports), which are not wired into the tenant
migration pipeline. Until they are, a tenant that holds any of the money- or
response-bearing rows below is refused at migration preflight/capture rather than
silently migrated without them; readable exports omit them (finance and answers are
never generic export material).
"""

_PENDING = ("Not yet portable: travels only through its package's custodial transform; a tenant holding "
            "these rows is refused by the tenant-migration preflight instead of losing them.")
_LEDGER = ("Core payout ledger: debt, payee envelopes and finance evidence are not yet portable; a tenant "
           "holding them is refused at migration preflight. Readable exports never carry finance history.")
_WORK = "Source-local work/coordination row; the target rebuilds it from imported domain rows."
_LOCATOR = "Permanent FK-free deletion locator: deployment custody that survives tenant purge; never tenant data."

PENDING_MODELS = (
    "events.EventStageForm", "events.EventStageMilestone", "events.StageFormAssignment",
    "events.StageFormResponse", "events.StageFormResponseRevision", "events.StageFormAsset",
    "event_reimbursements.ReimbursementProgramme", "event_reimbursements.ReimbursementBudgetPool",
    "event_reimbursements.BudgetReservation", "event_reimbursements.BudgetEntry",
    "event_reimbursements.GrantRequest", "event_reimbursements.GrantAward",
    "event_reimbursements.GrantAwardRevision", "event_reimbursements.ReimbursementClaim",
    "event_reimbursements.ClaimRevision", "event_reimbursements.ClaimLine",
    "event_reimbursements.ClaimDecision", "event_reimbursements.ClaimLineDecision",
    "event_reimbursements.ClaimAppeal", "event_reimbursements.ClaimScreeningReview",
    "event_reimbursements.ClaimAttendanceAttestation",
)
LEDGER_MODELS = (
    "payments.EventPayoutObligation", "payments.EventPayoutObligationRevision", "payments.EventPayoutEntry",
    "payments.EventPayeeRevision", "payments.EventPayeeReview", "payments.PayoutEligibility",
    "payments.PayoutHold", "payments.FinanceAttachment", "payments.ReceiptUse",
    "payments.ReceiptAllocationOverride", "payments.ReceiptAllocation",
    "payments.FinanceRetentionPolicy", "payments.FinanceRetentionPolicyRevision",
)
WORK_MODELS = (
    "events.StageActivationJob", "events.StageReconcileCursor", "event_reimbursements.ReimbursementWorkItem",
    "payments.EventPayoutCommandReceipt", "payments.PayoutExportBatch", "payments.PayoutExportBatchItem",
)
LOCATOR_MODELS = ("events.StageFileCleanup", "payments.FinanceObjectCleanup", "payments.FinanceSweepCursor")

OMITTED_MODELS = {
    **dict.fromkeys(PENDING_MODELS, _PENDING),
    **dict.fromkeys(LEDGER_MODELS, _LEDGER),
    **dict.fromkeys(WORK_MODELS, _WORK),
    **dict.fromkeys(LOCATOR_MODELS, _LOCATOR),
    "events.EventAttendanceCorrection": (
        "Correction watermarks only gate reimbursement eligibility, which never travels while "
        "reimbursement portability is refused."
    ),
}

# Columns this programme added to models that already travel. A registration's attendance
# counter is plain history; correction watermarks and claims that read it stay behind.
EXTRA_FIELDS = {"events.EventRegistration": "attendance_revision"}

# Tenant ownership path for the deployment backup's readable-main slicing. FK-free
# locators/cursors have none and stay deployment custody.
TENANT_OWNER_PATHS = {
    "events.EventStageForm": "event__makerspace",
    "events.EventStageMilestone": "event__makerspace",
    "events.StageFormAssignment": "event__makerspace",
    "events.StageFormResponse": "event__makerspace",
    "events.StageFormResponseRevision": "response__event__makerspace",
    "events.StageFormAsset": "event__makerspace",
    "events.StageActivationJob": "event__makerspace",
    "events.StageReconcileCursor": "event__makerspace",
    "events.EventAttendanceCorrection": "event__makerspace",
    "event_reimbursements.ReimbursementProgramme": "event__makerspace",
    "event_reimbursements.ReimbursementBudgetPool": "programme__event__makerspace",
    "event_reimbursements.BudgetReservation": "pool__programme__event__makerspace",
    "event_reimbursements.BudgetEntry": "pool__programme__event__makerspace",
    "event_reimbursements.GrantRequest": "event__makerspace",
    "event_reimbursements.GrantAward": "request__event__makerspace",
    "event_reimbursements.GrantAwardRevision": "award__request__event__makerspace",
    "event_reimbursements.ReimbursementClaim": "event__makerspace",
    "event_reimbursements.ReimbursementWorkItem": "event__makerspace",
    "event_reimbursements.ClaimRevision": "claim__event__makerspace",
    "event_reimbursements.ClaimLine": "revision__claim__event__makerspace",
    "event_reimbursements.ClaimDecision": "claim__event__makerspace",
    "event_reimbursements.ClaimLineDecision": "decision__claim__event__makerspace",
    "event_reimbursements.ClaimAppeal": "claim__event__makerspace",
    "event_reimbursements.ClaimScreeningReview": "claim__event__makerspace",
    "event_reimbursements.ClaimAttendanceAttestation": "event__makerspace",
    "payments.EventPayoutObligation": "makerspace",
    "payments.EventPayoutObligationRevision": "obligation__makerspace",
    "payments.EventPayoutEntry": "obligation__makerspace",
    "payments.EventPayeeRevision": "obligation__makerspace",
    "payments.EventPayeeReview": "obligation__makerspace",
    "payments.PayoutEligibility": "obligation__makerspace",
    "payments.PayoutHold": "obligation__makerspace",
    "payments.FinanceAttachment": "makerspace",
    "payments.ReceiptUse": "makerspace",
    "payments.ReceiptAllocationOverride": "receipt_use__makerspace",
    "payments.ReceiptAllocation": "receipt_use__makerspace",
    "payments.FinanceRetentionPolicy": "makerspace",
    "payments.FinanceRetentionPolicyRevision": "makerspace",
    "payments.EventPayoutCommandReceipt": "makerspace",
    "payments.PayoutExportBatch": "makerspace",
    "payments.PayoutExportBatchItem": "batch__makerspace",
}

_USER_REASON = "The owning row does not travel yet, so this person edge never joins the portable user closure."
USER_FIELDS = frozenset({
    ("events.EventAttendanceCorrection", "actor"), ("events.EventStageForm", "created_by"),
    ("events.EventStageMilestone", "member"), ("events.EventStageMilestone", "published_by"),
    ("events.StageFormAssignment", "owner_member"), ("events.StageFormAssignment", "extended_by"),
    ("events.StageFormAssignment", "cancelled_by"), ("events.StageFormAssignment", "reassigned_by"),
    ("events.StageFormResponse", "owner_member"), ("events.StageFormResponseRevision", "submitted_by"),
    ("events.StageFormAsset", "owner_member"), ("events.StageActivationJob", "actor"),
    ("event_reimbursements.ReimbursementProgramme", "created_by"),
    ("event_reimbursements.ReimbursementProgramme", "approved_by"),
    ("event_reimbursements.BudgetEntry", "actor"), ("event_reimbursements.GrantRequest", "member"),
    ("event_reimbursements.GrantRequest", "distance_verified_by"), ("event_reimbursements.GrantRequest", "reviewed_by"),
    ("event_reimbursements.GrantAward", "issued_by"), ("event_reimbursements.GrantAwardRevision", "actor"),
    ("event_reimbursements.ReimbursementClaim", "member"), ("event_reimbursements.ClaimRevision", "submitted_by"),
    ("event_reimbursements.ClaimDecision", "actor"), ("event_reimbursements.ClaimAppeal", "submitted_by"),
    ("event_reimbursements.ClaimScreeningReview", "reviewer"),
    ("event_reimbursements.ClaimAttendanceAttestation", "owner_member"),
    ("event_reimbursements.ClaimAttendanceAttestation", "actor"),
    ("payments.EventPayoutObligation", "owner_member"), ("payments.EventPayoutObligationRevision", "actor"),
    ("payments.EventPayoutEntry", "recorded_by"), ("payments.EventPayeeRevision", "owner"),
    ("payments.EventPayeeRevision", "verified_by"), ("payments.EventPayeeReview", "actor"),
    ("payments.PayoutEligibility", "acknowledged_by"), ("payments.PayoutHold", "actor"),
    ("payments.FinanceAttachment", "owner_member"), ("payments.ReceiptAllocationOverride", "actor"),
    ("payments.PayoutExportBatch", "created_by"), ("payments.EventPayoutCommandReceipt", "actor"),
    ("payments.FinanceRetentionPolicyRevision", "actor"),
})
EXCLUDED_USER_EDGE_REASONS = dict.fromkeys(USER_FIELDS, _USER_REASON)

# Rows whose presence makes a faithful tenant migration impossible today, by host path.
REFUSING_ROWS = {
    "events.EventStageForm": "event__makerspace_id",
    "event_reimbursements.ReimbursementProgramme": "event__makerspace_id",
    "payments.EventPayoutObligation": "makerspace_id",
    "payments.FinanceAttachment": "makerspace_id",
    "payments.FinanceRetentionPolicyRevision": "makerspace_id",
}


def unportable_row_labels(makerspace_id):
    """Model labels (sorted) whose rows would be lost by migrating this tenant now."""
    from django.apps import apps
    return sorted(label for label, path in REFUSING_ROWS.items()
                  if apps.get_model(label)._base_manager.filter(**{path: makerspace_id}).exists())
