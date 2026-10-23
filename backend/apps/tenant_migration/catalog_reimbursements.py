"""Export/Lane D dispositions for stage forms, reimbursements and the core payout ledger.

Every domain and ledger row travels in a portable tenant migration. The custodial
transforms in each package's ``portable.py`` run inside the importer: mandatory finance
envelopes (payee details, decision summaries) stay ciphertext in the archive and are
rebound to the target tenant key in memory only; typed IDs inside encrypted JSON are
remapped between decrypt and re-encrypt (``pii_reimbursements``); plaintext JSON and
UUID-valued references are remapped by ``semantic_reimbursements``. Imported
programmes arrive paused and stage assignments inert, so no money or deadline moves
on the target until staff reconcile. Readable exports never carry these rows.
"""

from .catalog_reimbursements_fields import FIELD_NAMES

_WORK = "Source-local work/coordination row; the target rebuilds it from imported domain rows."
_LOCATOR = "Permanent FK-free deletion locator: deployment custody that survives tenant purge; never tenant data."

STAGE_MODELS = (
    "events.EventStageForm", "events.EventStageMilestone", "events.StageFormAssignment",
    "events.StageFormResponse", "events.StageFormResponseRevision", "events.StageFormAsset",
    "events.EventAttendanceCorrection",
)
DOMAIN_MODELS = (
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
PORTABLE_MODELS = STAGE_MODELS + DOMAIN_MODELS + LEDGER_MODELS
WORK_MODELS = (
    "events.StageActivationJob", "events.StageReconcileCursor", "event_reimbursements.ReimbursementWorkItem",
    "payments.EventPayoutCommandReceipt", "payments.PayoutExportBatch", "payments.PayoutExportBatchItem",
)
LOCATOR_MODELS = ("events.StageFileCleanup", "payments.FinanceObjectCleanup", "payments.FinanceSweepCursor")

OMITTED_MODELS = {**dict.fromkeys(WORK_MODELS, _WORK), **dict.fromkeys(LOCATOR_MODELS, _LOCATOR)}
EXPORTED_FIELDS = {label: " ".join(sorted(FIELD_NAMES[label])) for label in PORTABLE_MODELS}

# Columns this programme added to models that already travel.
EXTRA_FIELDS = {"events.EventRegistration": "attendance_revision"}

# Tenant ownership path: deployment backup slicing and the portable dataset owner.
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


def _dataset_path(label):
    app, name = label.split(".")
    folder = "events/stages" if app == "events" else "finance/" + app
    return f"{folder}/{name}.csv"


DATASETS = {label: (_dataset_path(label), TENANT_OWNER_PATHS[label]) for label in PORTABLE_MODELS}

# Person edges of portable rows join the portable user closure; edges of work rows
# that never travel are excluded with a reason.
USER_FIELDS = frozenset({
    ("events.EventAttendanceCorrection", "actor"), ("events.EventStageForm", "created_by"),
    ("events.EventStageMilestone", "member"), ("events.EventStageMilestone", "published_by"),
    ("events.StageFormAssignment", "owner_member"), ("events.StageFormAssignment", "extended_by"),
    ("events.StageFormAssignment", "cancelled_by"), ("events.StageFormAssignment", "reassigned_by"),
    ("events.StageFormResponse", "owner_member"), ("events.StageFormResponseRevision", "submitted_by"),
    ("events.StageFormAsset", "owner_member"),
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
    ("payments.FinanceRetentionPolicyRevision", "actor"),
    ("events.StageActivationJob", "actor"), ("payments.PayoutExportBatch", "created_by"),
    ("payments.EventPayoutCommandReceipt", "actor"),
})
_WORK_EDGE = "Source-local work row; it never travels, so this person edge never joins the portable closure."
EXCLUDED_USER_EDGE_REASONS = {edge: _WORK_EDGE for edge in USER_FIELDS if edge[0] in WORK_MODELS}

# Every JSON column of a portable row, named so the reference registry reviews it.
# Typed ID slots inside them are remapped by semantic_reimbursements.
JSON_FIELDS = frozenset({
    ("events.EventStageForm", "reminder_offsets"), ("events.EventStageForm", "blocked_actions"),
    ("events.EventStageForm", "audience"), ("events.StageFormAssignment", "policy_snapshot"),
    ("events.StageFormAsset", "deletion_receipt"),
    ("event_reimbursements.ReimbursementProgramme", "tier_rules"),
    ("event_reimbursements.ReimbursementProgramme", "allowed_categories"),
    ("event_reimbursements.ReimbursementProgramme", "exclusions"),
    ("event_reimbursements.ReimbursementProgramme", "eligible_countries"),
    ("event_reimbursements.ReimbursementProgramme", "eligible_cohorts"),
    ("event_reimbursements.ReimbursementProgramme", "permitted_venue_sources"),
    ("event_reimbursements.ReimbursementProgramme", "category_limits"),
    ("event_reimbursements.GrantRequest", "category_estimates"),
    ("event_reimbursements.GrantAward", "calculation_snapshot"),
    ("event_reimbursements.GrantAwardRevision", "rule_snapshot"),
    ("event_reimbursements.ClaimAttendanceAttestation", "venue_evidence_refs"),
    ("payments.EventPayoutObligation", "eligibility_evidence"), ("payments.PayoutEligibility", "evidence"),
    ("payments.PayoutHold", "evidence_refs"), ("payments.FinanceAttachment", "deletion_receipt"),
    ("payments.ReceiptAllocationOverride", "allocation_snapshot"),
})
