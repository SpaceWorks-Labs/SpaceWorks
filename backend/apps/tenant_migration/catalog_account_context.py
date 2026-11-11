"""Account identity travels with people; source credential generations never do.

One account per person (U-D): a full user row is a person, whose staff roles are
staff-track memberships; merged shells, platform accounts and foreign provenance become
inert member stubs. ``staff_makerspace`` is empty for every account since the unification.
"""

from .tenant_dump_types import AuthorityDisposition as D, authority


AUTHORITY_ENTRIES = (
    *((('accounts.DeviceGrant', field), authority(
        D.DROP, 'Device account generation, login method and raw historical staff tenant never travel as target authority.',
    )) for field in ('staff_makerspace_id', 'credential_generation', 'login_method')),
    *((('accounts.StaffInvitation', field), authority(
        D.DROP, 'Initial-password role/scope/generation proofs are deployment-local and never travel.',
    )) for field in ('role_snapshot', 'machine_scope_snapshot', 'machine_ids_snapshot', 'credential_generation')),
    *((('notifications.NotificationPreference', field), authority(
        D.PRESERVE, "Staff-track holders' category/channel choices travel without provider endpoints or proof.",
    )) for field in ('makerspace', 'user', 'category', 'channels', 'email_fallback')),
    *((('makerspaces.MakerspaceMembership', field), authority(
        (D.PRESERVE, D.RESET),
        'Tenant staff roles and notification choices travel; member authority resets to Member.',
    )) for field in ('role', 'assigned_role', 'receives_notifications')),
    *((('makerspaces.MembershipAdditionalRole', field), authority(
        D.PRESERVE, 'Carried staff-track roles resolve by protected slug to target-seeded roles.',
    )) for field in ('membership', 'role', 'assigned_by', 'assigned_at')),
    *((('machines.MembershipMachineTypeScope', field), authority(
        D.PRESERVE, 'Carried staff-track machine reach follows its membership and remapped machine type.',
    )) for field in ('membership', 'machine_type')),
    *((('machines.MembershipMachineScope', field), authority(
        D.PRESERVE, 'Carried staff-track machine reach follows its membership and remapped machine.',
    )) for field in ('membership', 'machine')),
    (("accounts.User", "account_kind"), authority(
        (D.PRESERVE, D.RESET),
        "Keep people; shells and foreign/platform provenance become inert member stubs.",
    )),
    (("accounts.User", "staff_makerspace"), authority(
        (D.PRESERVE, D.RESET),
        "Empty since one account per person; legacy split-format values reset with stubs.",
    )),
    (("accounts.User", "retired_at"), authority(
        D.RESET, "Retired and merged shells never travel as live identities; stubs have no retirement authority.",
    )),
    (("accounts.User", "credential_generation"), authority(
        D.RESET, "Credential and invitation generations are source-local proof state, never target credentials.",
    )),
    (("accounts.StaffInvitation", "account"), authority(
        D.DROP, "Account-bound onboarding invitations and their bearer proofs never travel.",
    )),
)
