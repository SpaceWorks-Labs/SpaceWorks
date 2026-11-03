"""Audit presentation for staff roles on people and their email invitations (lane U-B).

Never an address or a code: invitations show only the role slugs, the machine scopes,
an address fingerprint and the expiry. ``account.disabled`` is the superadmin's
/control/ action (Q8).
"""

from .presentation_catalog_types import P

ENTRIES = (
    P("staff_role.changed", "Staff role changed",
      ("membership_id", "before.roles", "before.machine_type_ids", "after.roles", "after.machine_type_ids")),
    P("staff_role.revoked", "Staff role revoked", ("membership_id", "reason")),
    P("staff_role.restored", "Staff role restored", ("membership_id",)),
    P("staff_invitation.sent", "Staff invitation sent", ("roles", "machine_type_ids", "email_hash", "expires_at")),
    P("staff_invitation.accepted", "Staff invitation accepted", ("membership_id", "roles")),
    P("staff_invitation.accept_failed", "Staff invitation code rejected"),
    P("staff_invitation.revoked", "Staff invitation revoked"),
    P("account.disabled", "Account disabled by the platform administrator", ("reason",)),
    P("account.enabled", "Account re-enabled by the platform administrator"),
)
