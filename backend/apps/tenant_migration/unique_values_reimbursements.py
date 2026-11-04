"""Deployment-global uniqueness decisions for portable stage, reimbursement and payout rows.

Opaque identities (domain ``uuid`` columns, stage ``form_id`` and every idempotency
``operation_id``) are preserved verbatim: other rows, digests and encrypted summaries
refer to them by value. A collision on the target is a contradiction and refuses the
import. Object and staging keys follow the target's own allocation.
"""
from .insertion_errors import ArchiveFormatError
from .unique_values_policy import PRESERVE, REMAP, _policy


def _refuse(label, name):
    def refuse(row, target, value):
        raise ArchiveFormatError(f"{label}.{name} already holds this opaque identity on the target; import refused.")
    refuse.refuses_collision = True
    return refuse

_KEEP = "Preserve immutable opaque identity referenced by value; a target collision refuses the import."
_KEYS = "Target object journal and fresh coordination locators allocate these keys."
_OWNED = "Typed owners follow the target allocation; a duplicate tuple refuses."

_PRESERVED = (
    ("events.EventStageForm", "form_id"),
    ("events.EventAttendanceCorrection", "operation_id"),
    ("event_reimbursements.ReimbursementProgramme", "initialization_operation_id"),
    ("event_reimbursements.GrantRequest", "uuid"),
    ("event_reimbursements.GrantAward", "uuid"),
    ("event_reimbursements.ReimbursementClaim", "uuid"),
    ("event_reimbursements.ClaimDecision", "uuid"),
    ("event_reimbursements.ClaimAttendanceAttestation", "uuid"),
    ("event_reimbursements.ClaimAttendanceAttestation", "operation_id"),
    ("payments.EventPayoutObligationRevision", "operation_id"),
    ("payments.EventPayoutEntry", "operation_id"),
    ("payments.EventPayeeReview", "operation_id"),
    ("payments.PayoutHold", "operation_id"),
    ("payments.ReceiptAllocationOverride", "operation_id"),
    ("payments.FinanceRetentionPolicyRevision", "operation_id"),
)
RULES = {
    **{(label, f"field:{name}"): _policy(PRESERVE, _KEEP, field=name, generator=_refuse(label, name))
       for label, name in _PRESERVED},
    # One obligation per source claim across the deployment: the claim uuid is preserved.
    ("payments.EventPayoutObligation", "payout_unique_source"): _policy(
        PRESERVE, _KEEP, field="source_uuid", generator=_refuse("payments.EventPayoutObligation", "source_uuid")),
    **{key: _policy(REMAP, _OWNED) for key in (
        ("event_reimbursements.BudgetReservation", "field:award"),
        ("event_reimbursements.GrantRequest", "reimb_request_unique_owner"),
        ("event_reimbursements.ReimbursementClaim", "field:award"),
        ("events.EventAttendanceCorrection", "event_attendance_correction_revision"),
        ("events.StageFormAssignment", "stage_assignment_unique_owner"),
        ("events.StageFormResponse", "field:assignment"),
        ("payments.EventPayeeReview", "payout_payee_review_sequence"),
        ("payments.EventPayoutEntry", "field:amends"),
        ("payments.EventPayoutObligationRevision", "field:previous_revision"),
        ("payments.EventPayoutObligationRevision", "payout_decision_origin_unique"),
        ("payments.PayoutHold", "field:releases"),
    )},
    **{(label, f"field:{name}"): _policy(REMAP, _KEYS)
       for label in ("events.StageFormAsset", "payments.FinanceAttachment") for name in ("object_key", "staging_key")},
}
