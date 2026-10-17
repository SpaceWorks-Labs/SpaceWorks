"""D11/V5 account identity travels; source credential generations never do."""

from .tenant_dump_types import AuthorityDisposition as D, authority


AUTHORITY_ENTRIES = (
    *((('makerspaces.MakerspaceMembership', field), authority(
        (D.PRESERVE, D.RESET),
        'Tenant staff roles and notification choices travel; member authority resets to Member.',
    )) for field in ('role', 'assigned_role', 'receives_notifications')),
    *((('makerspaces.MembershipAdditionalRole', field), authority(
        D.PRESERVE, 'Carried tenant staff roles resolve by protected slug to target-seeded roles.',
    )) for field in ('membership', 'role', 'assigned_by', 'assigned_at')),
    *((('machines.MembershipMachineTypeScope', field), authority(
        D.PRESERVE, 'Carried staff machine reach follows its membership and remapped machine type.',
    )) for field in ('membership', 'machine_type')),
    (("accounts.User", "account_kind"), authority(
        (D.PRESERVE, D.RESET),
        "Keep tenant member/staff identity; replace foreign/platform provenance with an inert member stub.",
    )),
    (("accounts.User", "staff_makerspace"), authority(
        (D.PRESERVE, D.RESET),
        "A full staff account belongs to the exiting tenant; foreign provenance stubs carry no staff owner.",
    )),
    (("accounts.User", "retired_at"), authority(
        D.RESET, "Retired shells never travel as live tenant identities; stubs have no retirement authority.",
    )),
    (("accounts.User", "credential_generation"), authority(
        D.RESET, "Credential and invitation generations are source-local proof state, never target credentials.",
    )),
    (("accounts.StaffInvitation", "account"), authority(
        D.DROP, "Account-bound onboarding invitations and their bearer proofs never travel.",
    )),
)
