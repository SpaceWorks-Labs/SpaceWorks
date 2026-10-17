"""Migration evidence: remap memberships; deleted role identities stay source-local."""

from .audit_references_targets import AuditReference, AuditReferenceDisposition

R = AuditReferenceDisposition.REMAP
S = AuditReferenceDisposition.SOURCE_LOCAL_SNAPSHOT

FIXED_ROLE_AUDIT_EDGES = {
    ("staff.account_created", "membership_id"): AuditReference(R, "makerspaces.MakerspaceMembership"),
    ("staff.account_created", "machine_type_ids"): AuditReference(R, "machines.MachineType"),
    **{(action, "removed_machine_type_ids"): AuditReference(R, "machines.MachineType")
       for action in ("staff.invitation_accepted", "membership.joined", "membership.approved",
                      "membership.adopted_from_import")},
    ("staff.roles_changed", "membership_id"): AuditReference(R, "makerspaces.MakerspaceMembership"),
    ("staff.roles_changed", "removed_machine_type_ids"): AuditReference(R, "machines.MachineType"),
    ("staff.machine_scope_changed", "membership_id"): AuditReference(R, "makerspaces.MakerspaceMembership"),
    ("staff.machine_scope_changed", "user_id"): AuditReference(S, "accounts.User"),
    ("staff.machine_scope_changed", "before"): AuditReference(R, "machines.MachineType"),
    ("staff.machine_scope_changed", "after"): AuditReference(R, "machines.MachineType"),
    ("membership.role_changed", "role_ids"): AuditReference(S, "makerspaces.MakerspaceRole"),
    ("staff.roles_migrated", "membership_id"): AuditReference(R, "makerspaces.MakerspaceMembership"),
    ("staff.roles_migrated", "membership_request_id"): AuditReference(R, "makerspaces.MembershipRequest"),
    ("staff.roles_migrated", "from_role.id"): AuditReference(S, "makerspaces.MakerspaceRole"),
    ("staff.roles_migrated", "old_role_id"): AuditReference(S, "makerspaces.MakerspaceRole"),
    ("staff.roles_migrated", "invitation_id"): AuditReference(S, "accounts.StaffInvitation"),
    ("staff.roles_migrated", "machine_scope.from.types"): AuditReference(S, "machines.MachineType"),
    ("staff.roles_migrated", "machine_scope.from.machines"): AuditReference(S, "machines.Machine"),
    ("staff.roles_migrated", "machine_scope.to.types"): AuditReference(R, "machines.MachineType"),
    ("staff.roles_migrated", "machine_scope.to.machines"): AuditReference(S, "machines.Machine"),
    ("staff.roles_migrated", "machine_scope.dropped_machine_ids"): AuditReference(S, "machines.Machine"),
    ("staff.invitation_revoked_by_migration", "invitation_id"): AuditReference(S, "accounts.StaffInvitation"),
    ("staff.invitation_revoked_by_migration", "old_role_id"): AuditReference(S, "makerspaces.MakerspaceRole"),
    ("report_schedule.recipients_pruned_by_migration", "schedule_id"): AuditReference(R, "operations.ReportSchedule"),
}
