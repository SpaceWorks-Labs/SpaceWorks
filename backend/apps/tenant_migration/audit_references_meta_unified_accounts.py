"""Audit meta references for release-2 lane U-A1 (one account per person).

`staff_role.granted` names the new staff-track membership and its machine scopes, both
tenant rows that remap; U-B's change, restore, revoke and invitation events name the same
rows. `account.converted` carries no ids (field names and role slugs).
"""

from .audit_references_targets import AuditReference, AuditReferenceDisposition

R = AuditReferenceDisposition.REMAP

UNIFIED_ACCOUNT_AUDIT_EDGES = {
    ("staff_role.granted", "membership_id"): AuditReference(R, "makerspaces.MakerspaceMembership"),
    ("staff_role.granted", "machine_type_ids"): AuditReference(R, "machines.MachineType"),
    # Release 2 U-B: staff roles on people and signed-in staff invitations.
    **{(action, "membership_id"): AuditReference(R, "makerspaces.MakerspaceMembership")
       for action in ("staff_role.changed", "staff_role.restored", "staff_role.revoked",
                      "staff_invitation.accepted")},
    ("staff_invitation.sent", "machine_type_ids"): AuditReference(R, "machines.MachineType"),
}
