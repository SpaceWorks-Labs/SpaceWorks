"""r2-superadmin-controls (#185, #187A): space controls, onboarding, announcements and
the managed-hosting limiter. Leaves are states, counts, ids, dates and field NAMES:
never a reason, a note, an announcement body or a provider secret."""

from .presentation_catalog_types import P

ENTRIES = (
    P("space_control.suspended", "Space paused by the platform operator", ("read_only",)),
    P("space_control.unsuspended", "Space unblocked by the platform operator", ("read_only",)),
    P("space_control.read_only_enabled", "Space put in read-only mode", ("source",)),
    P("space_control.read_only_lifted", "Read-only mode ended", ("source",)),
    P("space_control.schedule_set", "Archive and purge scheduled", ("archive_on", "purge_due_at", "purge_grace_days")),
    P("space_control.schedule_cancelled", "Scheduled archive or purge cancelled"),
    P("space_control.schedule_blocked", "Scheduled archive or purge held", ("reason",)),
    P("space_control.schedule_cleared", "Scheduled purge cleared", ("reason",)),
    P("space_control.scheduled_archive_ran", "Space archived as scheduled", ("purge_due_at",)),
    P("space_control.scheduled_purge_ran", "Space purged as scheduled", ("makerspace_id", "slug")),
    P("space_control.ownership_invited", "New Space Manager invited (ownership transfer)", ("invitation_id",)),
    P("space_control.ownership_transferred", "Space ownership transferred",
      ("new_user_id", "previous_user_id", "previous_outcome")),
    P("space_control.space_onboarded", "Space created from a hosting request", ("hosting_request_id", "manager_invited")),
    P("space_control.superadmin_bypass", "Superadmin acted in a paused or read-only space",
      ("bypass_space_control", "path")),
    P("space_control.announcement_created", "Platform announcement created",
      ("severity", "audience", "space_count", "send_email", "show_to_members")),
    P("space_control.announcement_cancelled", "Platform announcement cancelled"),
    P("space_control.announcement_emailed", "Platform announcement emailed", ("recipient_count",)),
    P("managed_hosting.plan_created", "Hosting plan created", ("fields",)),
    P("managed_hosting.plan_updated", "Hosting plan changed", ("fields",)),
    P("managed_hosting.plan_assigned", "Hosting plan assigned", ("plan_id", "trial_days")),
    P("managed_hosting.plan_removed", "Hosting plan removed"),
    P("managed_hosting.trial_expired", "Hosting trial ended", ("plan_id",)),
    P("managed_hosting.invoice_created", "Hosting invoice recorded", ("amount_minor", "currency", "due_on")),
    P("managed_hosting.invoice_paid", "Hosting invoice paid", ("method", "amount_minor")),
    P("managed_hosting.invoice_voided", "Hosting invoice voided"),
    P("managed_hosting.billing_settings_updated", "Hosting billing settings changed", ("fields",)),
)
