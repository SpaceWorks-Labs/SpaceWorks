"""Audit metadata IDs written by parity lane E-B6 (refund-driven ticket cancellation, staff expense claims)."""

from .audit_references_targets import AuditReference, AuditReferenceDisposition

R = AuditReferenceDisposition.REMAP
_TICKETS = ("payment.refund_case_tickets_cancelled", "payment.refund_case_tickets_cancel_failed")
# Reimbursement rows are not part of a tenant export yet, so a request id stays an inert source snapshot.
_INERT = AuditReference(AuditReferenceDisposition.SOURCE_LOCAL_SNAPSHOT, None, "reimbursement_source_provenance")

EDGES = {
    **{(action, "case_id"): AuditReference(R, "payments.RefundCase") for action in _TICKETS},
    **{(action, "payment_id"): AuditReference(R, "payments.Payment") for action in _TICKETS},
    ("event.reimbursement.staff_claim_filed", "request_id"): _INERT,
}
