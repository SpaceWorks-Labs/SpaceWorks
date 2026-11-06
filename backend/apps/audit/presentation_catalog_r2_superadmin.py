"""r2-superadmin-controls (#185, #187A): space controls, onboarding, announcements and
the managed-hosting limiter. Leaves are states, counts, ids, dates and field NAMES:
never a reason, a note, an announcement body or a provider secret."""

from django.utils.translation import gettext_lazy
from .presentation_catalog_types import P

ENTRIES = (
    P("space_control.suspended", gettext_lazy("Space paused by the platform operator"), ("read_only",)),
    P("space_control.unsuspended", gettext_lazy("Space unblocked by the platform operator"), ("read_only",)),
    P("space_control.read_only_enabled", gettext_lazy("Space put in read-only mode"), ("source",)),
    P("space_control.read_only_lifted", gettext_lazy("Read-only mode ended"), ("source",)),
    P("space_control.schedule_set", gettext_lazy("Archive and purge scheduled"), ("archive_on", "purge_due_at", "purge_grace_days")),
    P("space_control.schedule_cancelled", gettext_lazy("Scheduled archive or purge cancelled")),
    P("space_control.schedule_blocked", gettext_lazy("Scheduled archive or purge held"), ("reason",)),
    P("space_control.schedule_cleared", gettext_lazy("Scheduled purge cleared"), ("reason",)),
    P("space_control.scheduled_archive_ran", gettext_lazy("Space archived as scheduled"), ("purge_due_at",)),
    P("space_control.scheduled_purge_ran", gettext_lazy("Space purged as scheduled"), ("makerspace_id", "slug")),
    P("space_control.ownership_invited", gettext_lazy("New Space Manager invited (ownership transfer)"), ("invitation_id",)),
    P("space_control.ownership_transferred", gettext_lazy("Space ownership transferred"),
      ("new_user_id", "previous_user_id", "previous_outcome")),
    P("space_control.space_onboarded", gettext_lazy("Space created from a hosting request"), ("hosting_request_id", "manager_invited")),
    P("space_control.superadmin_bypass", gettext_lazy("Superadmin acted in a paused or read-only space"),
      ("bypass_space_control", "path")),
    P("space_control.announcement_created", gettext_lazy("Platform announcement created"),
      ("severity", "audience", "space_count", "send_email", "show_to_members")),
    P("space_control.announcement_cancelled", gettext_lazy("Platform announcement cancelled")),
    P("space_control.announcement_emailed", gettext_lazy("Platform announcement emailed"), ("recipient_count",)),
    P("managed_hosting.plan_created", gettext_lazy("Hosting plan created"), ("fields",)),
    P("managed_hosting.plan_updated", gettext_lazy("Hosting plan changed"), ("fields",)),
    P("managed_hosting.plan_assigned", gettext_lazy("Hosting plan assigned"), ("plan_id", "trial_days")),
    P("managed_hosting.plan_removed", gettext_lazy("Hosting plan removed")),
    P("managed_hosting.trial_expired", gettext_lazy("Hosting trial ended"), ("plan_id",)),
    P("managed_hosting.invoice_created", gettext_lazy("Hosting invoice recorded"), ("amount_minor", "currency", "due_on")),
    P("managed_hosting.invoice_paid", gettext_lazy("Hosting invoice paid"), ("method", "amount_minor")),
    P("managed_hosting.invoice_voided", gettext_lazy("Hosting invoice voided")),
    P("managed_hosting.billing_settings_updated", gettext_lazy("Hosting billing settings changed"), ("fields",)),
)
