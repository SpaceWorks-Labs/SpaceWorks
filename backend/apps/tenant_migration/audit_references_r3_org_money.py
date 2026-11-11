"""Parity O-B3 audit meta ids: a plan travels with the space and remaps; a collector is an account id."""
from .audit_references_targets import AuditReference, AuditReferenceDisposition

R = AuditReferenceDisposition.REMAP
S = AuditReferenceDisposition.SOURCE_LOCAL_SNAPSHOT

EDGES = {
    ("membership_plan.sac_changed", "plan_id"): AuditReference(R, "makerspaces.MembershipPlan"),
    ("payment.cash_handover_recorded", "collector_id"): AuditReference(S, "accounts.User"),
}
