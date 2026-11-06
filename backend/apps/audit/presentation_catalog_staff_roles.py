"""Audit presentation for staff roles on people and their email invitations (lane U-B).

Never an address or a code: invitations show only the role slugs, the machine scopes,
an address fingerprint and the expiry. Free-text reasons are stored but never shown.
``account.disabled`` is the superadmin's /control/ action (Q8). The release-1 staff-account
actions (``staff_account.*``, ``staff.account_created``, ``staff.invitation_*``) are no longer
emitted, so their entries are gone.
"""

from django.utils.translation import gettext_lazy
from .presentation_catalog_types import P

ENTRIES = (
    P("staff_role.changed", gettext_lazy("Staff role changed"),
      ("membership_id", "roles_before", "roles_after", "machine_type_ids_before", "machine_type_ids_after")),
    P("staff_role.revoked", gettext_lazy("Staff role revoked"), ("membership_id",)),
    P("staff_role.restored", gettext_lazy("Staff role restored"), ("membership_id",)),
    P("staff_invitation.sent", gettext_lazy("Staff invitation sent"), ("roles", "machine_type_ids", "email_hash", "expires_at")),
    P("staff_invitation.accepted", gettext_lazy("Staff invitation accepted"), ("membership_id", "roles")),
    P("staff_invitation.accept_failed", gettext_lazy("Staff invitation code rejected")),
    P("staff_invitation.revoked", gettext_lazy("Staff invitation revoked")),
    P("account.disabled", gettext_lazy("Account disabled by the platform administrator")),
    P("account.enabled", gettext_lazy("Account re-enabled by the platform administrator")),
)
