"""Explicit target row dispositions, including source-local coordination."""

from .target_projection_types import RowDisposition, RowPolicy
from .projection_wp4 import ROW_POLICIES as WP4_ROW_POLICIES
from .catalog_p2_presence import DROP_MODELS as PRESENCE_DROPS


ROW_POLICIES = {
    **{label: RowPolicy(RowDisposition.DROP, reason) for label, reason in PRESENCE_DROPS.items()},
    "events.EventCertificateArtwork": RowPolicy(
        RowDisposition.DROP,
        "Unpromoted upload reservations have no durable artwork or portable authority.",
        condition=("promoted_at", None),
    ),
    "makerspaces.MembershipAdditionalRole": RowPolicy(RowDisposition.DROP, "Imported memberships are reduced to Member; additional authority is dropped.", condition=("_staff_account", False)),
    "machines.MembershipMachineScope": RowPolicy(RowDisposition.DROP, "Imported memberships carry no machine-management authority.", condition=("_staff_account", False)),
    "machines.MembershipMachineTypeScope": RowPolicy(RowDisposition.DROP, "Imported memberships carry no machine-management authority.", condition=("_staff_account", False)),
    **WP4_ROW_POLICIES,
    "makerspaces.MakerspaceLoanPolicy": RowPolicy(
        RowDisposition.PRESERVE_LIVE,
        "Tenant loan preferences travel; target-owned feature switches still gate renewals and limits.",
    ),
    # machines.MakerspaceMachineTypePolicy uses the ordinary data projection;
    # numeric preferences carry no actor or authority grants.
    "notifications.MemberNotificationPreference": RowPolicy(RowDisposition.DROP, "Only staff notification preferences travel.", condition=("_staff_account", False)),
    "notifications.NotificationPreference": RowPolicy(RowDisposition.DROP, "Only staff category/channel choices travel; endpoints require fresh proof.", condition=("_staff_account", False)),
    "notifications.NotificationInboxRow": RowPolicy(RowDisposition.DROP, "Source inbox text and read state are delivery telemetry."),
    "integrations.EmailSuppression": RowPolicy(RowDisposition.DROP, "Deployment-keyed suppressed addresses do not travel."),
    "operations.ReminderSchedule": RowPolicy(
        RowDisposition.DROP,
        "Source-local reminder coordination is rebuilt by target sources; claims never travel.",
    ),
    "makerspaces.Station": RowPolicy(
        RowDisposition.STAGE_INERT,
        "Portable Station metadata has no credential and contributes no live authority edges.",
    ),
    "machines.MachineOperator": RowPolicy(
        RowDisposition.PRESERVE_LIVE,
        "Owner decision 22: preserve the exact live machine grant and provenance.",
    ),
    "makerspaces.MakerspaceRole": RowPolicy(RowDisposition.KEEP_TARGET, "Target-seeded roles are authoritative; archived role rows are dropped."),
    "integrations.NotificationRecipient": RowPolicy(RowDisposition.DROP, "Every explicit recipient kind is a live disclosure rule."),
    "integrations.RecipientMachineTypeScope": RowPolicy(RowDisposition.DROP, "A child of a dropped recipient cannot arrive live."),
    "integrations.RecipientMachineScope": RowPolicy(RowDisposition.DROP, "A child of a dropped recipient cannot arrive live."),
    "integrations.RecipientCategoryScope": RowPolicy(RowDisposition.DROP, "A child of a dropped recipient cannot arrive live."),
    "operations.ReportSchedule": RowPolicy(RowDisposition.DROP, "A scheduled report delivery is a live disclosure rule the target must re-create."),
    "integrations.NotificationDestination": RowPolicy(
        RowDisposition.STAGE_INERT,
        "Imported Telegram rooms require target-authorized activation.",
        condition=("channel", "telegram"),
    ),
    # Open source-authored requests/invitations are target admission capability.
    # Dropping both open states prevents a later claim/approval from granting target
    # membership; active/revoked history may still import.
    "makerspaces.MembershipRequest": RowPolicy(
        RowDisposition.DROP,
        "Imported invitations are authority the target never authorized and must be re-created.",
        condition=("state", frozenset({"requested", "invited", "awaiting_vouches", "changes_requested"})),
    ),
}
