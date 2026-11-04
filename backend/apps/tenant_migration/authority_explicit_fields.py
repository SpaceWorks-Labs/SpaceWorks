"""Reviewed authority/disclosure declarations (split from `authority_guards.py`).

``EXPLICIT_AUTHORITY_FIELDS`` names each exported authorization input the threat model
identified, with the reason importing it grants no target authority. Re-exported from
``authority_guards``; import it from there.
"""
from .authority_reconciliation import AUTHORITY_FIELDS as RECONCILIATION_FIELDS
from .authority_resource_fields import RESOURCE_AUTHORITY_FIELDS
from .authority_wp4 import AUTHORITY_FIELDS as WP4_AUTHORITY_FIELDS
from .tenant_dump_authority_loans import LOAN_AUTHORITY_FIELDS

EXPLICIT_AUTHORITY_FIELDS = {
    **RECONCILIATION_FIELDS,
    ("makerspaces.MakerspaceMembership", "renewal_cancelled_at"): (
        "Historical cancellation stops source renewal; target automation resets independently."
    ),
    ("makerspaces.MembershipAdditionalRole", "membership"): "Dropped membership role authority.",
    ("makerspaces.MembershipAdditionalRole", "role"): "Dropped additional role authority.",
    ("makerspaces.MembershipAdditionalRole", "assigned_by"): "Dropped role assignment provenance.",
    ("makerspaces.MembershipAdditionalRole", "assigned_at"): "Dropped role assignment time.",
    ("machines.MembershipMachineTypeScope", "membership"): "Dropped membership machine authority.",
    ("machines.MembershipMachineTypeScope", "machine_type"): "Dropped membership type authority.",
    **WP4_AUTHORITY_FIELDS,
    **RESOURCE_AUTHORITY_FIELDS,
    **LOAN_AUTHORITY_FIELDS,
    ("makerspaces.Makerspace", "location"): "AST over-approximation from broadcast rendering; portable location grants no authority.",
    ("machines.Machine", "location"): "AST over-approximation from broadcast rendering; portable location grants no authority.",
    ("machines.MakerspaceMachineTypePolicy", "makerspace"): "Tenant boundary for reminder policy; preserved data does not grant staff authority.",
    ("machines.MakerspaceMachineTypePolicy", "machine_type"): "Remapped type boundary for reminder policy, never an authorization scope grant.",
    ("machines.MakerspaceMachineTypePolicy", "cert_reminder_days"): "Portable certification disclosure timing; target-owned feature and channel gates still apply.",
    ("machines.MakerspaceMachineTypePolicy", "reminder_lead_days"): "Portable maintenance disclosure timing; recipients require live target machine authority.",
    ("machines.MakerspaceMachineTypePolicy", "grace_days"): "Portable overdue disclosure timing; grants no access or automatic lockout bypass.",
    ("maintenance.MaintenanceSchedule", "anchor"): "Portable recurrence preference; completion still requires target actor authority.",
    ("makerspaces.Makerspace", "lifecycle_state"): (
        "Scheduled-work visibility is target-owned; Lane D resets lifecycle state."
    ),
    ("makerspaces.MakerspaceMembership", "makerspace"): "Tenant boundary for membership authority.",
    ("makerspaces.MakerspaceMembership", "user"): "Identity receiving the membership grant.",
    ("makerspaces.MakerspaceMembership", "role"): "Legacy fallback authority is reduced to Member/CUSTOM.",
    ("makerspaces.MakerspaceMembership", "assigned_role"): "Remapped only to the target Member role.",
    ("makerspaces.MakerspaceMembership", "status"): "Preserved only as inert pending-membership evidence until target proof.",
    ("makerspaces.MakerspaceRole", "makerspace"): "Target-seeded role ownership boundary.",
    ("makerspaces.MakerspaceRole", "slug"): "Identifies the target-seeded Member role.",
    ("makerspaces.MakerspaceRole", "granted_actions"): "Archived role rows are dropped; target grants are kept.",
    ("makerspaces.MakerspaceRole", "legacy_role"): "Archived role rows are dropped; target identity is kept.",
    ("makerspaces.MakerspaceRole", "is_default"): "Required when resolving the protected target Member role.",
    ("makerspaces.MakerspaceRole", "is_protected"): "Required when resolving the protected target Member role.",
    ("machines.Machine", "makerspace"): "Machine authorization is bounded by this tenant relation.",
    ("machines.Machine", "machine_type"): "Type-level authority follows this remapped relation.",
    ("machines.Machine", "status"): "AST over-approximation: operational state remains archive evidence.",
    ("machines.Machine", "is_active"): "AST over-approximation: lifecycle state remains archive evidence.",
    ("machines.MachineType", "makerspace"): "Distinguishes target globals from tenant custom types.",
    ("machines.MachineType", "is_builtin"): "Discriminator for global resolution versus projected custom insertion.",
    ("machines.MachineType", "slug"): "Resolves target built-in types; custom type identifiers stay tenant-scoped.",
    ("makerspaces.Makerspace", "slug"): "Portable routing identifier is resolved for the new tenant; it grants no actor authority.",
    ("makerspaces.Makerspace", "public_inventory_enabled"): "Portable catalogue publication choice remains bounded by target modules, loan visibility and servability.",
    ("machines.MachineOperator", "machine"): "Owner decision 22 preserves this live authority relation.",
    ("machines.MachineOperator", "user"): "Owner decision 22 preserves the identity receiving authority.",
    ("machines.MachineOperator", "access_level"): "Owner decision 22 preserves the operate/manage/full grant.",
    ("machines.MachineOperator", "assigned_by"): "Owner decision 22 preserves assignment provenance with FK closure.",
    ("machines.MachineOperator", "assigned_at"): "Owner decision 22 preserves assignment-time provenance.",
    ("makerspaces.MembershipRequest", "assigned_role"): "Remapped to target Member, never a source role.",
    ("integrations.NotificationRecipient", "makerspace"): "Dropped disclosure-rule tenant boundary.",
    ("integrations.NotificationRecipient", "feature"): "Dropped disclosure-rule discriminator.",
    ("integrations.NotificationRecipient", "event"): "Dropped disclosure-rule discriminator.",
    ("integrations.NotificationRecipient", "kind"): "Every recipient kind is dropped.",
    ("integrations.NotificationRecipient", "role"): "Dropped role-directed disclosure rule.",
    ("integrations.NotificationRecipient", "user"): "Dropped named-user disclosure rule.",
    ("integrations.NotificationDestination", "channel"): "Selects credential and delivery semantics.",
    ("integrations.NotificationDestination", "telegram_chat_id"): "Target-bot disclosure destination.",
    # Release 2 L4: an AST over-approximation (`source` is a common keyword); the
    # membership's join/manual/import label is provenance and grants no authority.
    ("makerspaces.MakerspaceMembership", "source"): "Join-path provenance label; grants no target authority.",
}

# Release 2 L12: per-type job settings travel as the space's own configuration (catalog_l12).
from .catalog_l12 import POLICY_FIELDS as _L12_POLICY_FIELDS  # noqa: E402
EXPLICIT_AUTHORITY_FIELDS.update({
    ("machines.MakerspaceMachineTypePolicy", name): "Portable per-type job setting; grants no staff authority."
    for name in _L12_POLICY_FIELDS.split()
})
