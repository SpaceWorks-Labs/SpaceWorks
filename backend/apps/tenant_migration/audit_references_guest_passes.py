"""Decision 223 audit meta ids: passes and their charges travel and remap; account ids are source snapshots."""
from .audit_references_targets import AuditReference, AuditReferenceDisposition

R = AuditReferenceDisposition.REMAP
S = AuditReferenceDisposition.SOURCE_LOCAL_SNAPSHOT

EDGES = {
    ("membership.guest_pass_issued", "holder_id"): AuditReference(S, "accounts.User"),
    ("membership.guest_pass_issued", "sponsor_id"): AuditReference(S, "accounts.User"),
    ("membership.guest_pass_converted", "membership_id"): AuditReference(R, "makerspaces.MakerspaceMembership"),
    ("membership.guest_pass_charge_raised", "payment_id"): AuditReference(R, "payments.Payment"),
    ("membership.guest_pass_charge_raised", "product_id"): AuditReference(R, "makerspaces.DayPassProduct"),
}
