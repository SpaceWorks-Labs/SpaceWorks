"""Decision 223 (k), lane L3b audit meta ids: rows that travel remap; account ids are source snapshots."""
from .audit_references_targets import AuditReference, AuditReferenceDisposition

R = AuditReferenceDisposition.REMAP
S = AuditReferenceDisposition.SOURCE_LOCAL_SNAPSHOT

EDGES = {
    ("membership.volunteer_credit_applied", "payment_id"): AuditReference(R, "payments.Payment"),
    ("booking.organization_linked", "organization_id"): AuditReference(S, "organizations.Organization"),
}
