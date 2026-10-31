"""Audit meta references for release-2 lane U-A1 (one account per person).

`staff_role.granted` names the new staff-track membership and its machine scopes, both
tenant rows that remap. `account.converted` carries no ids (field names and role slugs).
"""

from .audit_references_targets import AuditReference, AuditReferenceDisposition

R = AuditReferenceDisposition.REMAP

UNIFIED_ACCOUNT_AUDIT_EDGES = {
    ("staff_role.granted", "membership_id"): AuditReference(R, "makerspaces.MakerspaceMembership"),
    ("staff_role.granted", "machine_type_ids"): AuditReference(R, "machines.MachineType"),
}
