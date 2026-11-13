"""Parity O-B1 audit meta ids: units, memberships and plans travel with the space and remap."""
from .audit_references_targets import AuditReference, AuditReferenceDisposition

R = AuditReferenceDisposition.REMAP
UNIT, MEMBERSHIP = "makerspaces.MemberUnit", "makerspaces.MakerspaceMembership"

EDGES = {
    **{(action, key): AuditReference(R, UNIT) for action, key in (
        ("member_unit.created", "unit_id"), ("member_unit.created", "parent_id"),
        ("member_unit.updated", "unit_id"), ("member_unit.moved", "unit_id"), ("member_unit.moved", "parent_id"),
        ("member_unit.archived", "unit_id"), ("member_unit.restored", "unit_id"),
        ("member_unit.import_reviewed", "unit_id"),
        ("membership.unit_changed", "from_unit_id"), ("membership.unit_changed", "to_unit_id"),
        ("staff.unit_scope_changed", "from_unit_id"), ("staff.unit_scope_changed", "to_unit_id"),
        ("membership_plan.units_changed", "unit_ids"), ("membership.invite_link_created", "unit_id"))},
    ("member_unit.import_reviewed", "imported_member_id"): AuditReference(R, "makerspaces.ImportedMember"),
    ("membership.unit_changed", "membership_id"): AuditReference(R, MEMBERSHIP),
    ("staff.unit_scope_changed", "membership_id"): AuditReference(R, MEMBERSHIP),
    ("membership_plan.units_changed", "plan_id"): AuditReference(R, "makerspaces.MembershipPlan"),
}
