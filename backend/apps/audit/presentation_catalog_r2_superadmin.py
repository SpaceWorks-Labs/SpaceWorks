"""r2-superadmin-controls (#185, #187A): space controls, onboarding, announcements and
the managed-hosting limiter. Leaves are states, counts, ids, dates and field NAMES:
never a reason, a note, an announcement body or a provider secret."""

from django.utils.translation import gettext_noop
from .presentation_catalog_types import P

ENTRIES = (
    P("space_control.suspended", gettext_noop("Space paused by the platform operator"), ("read_only",)),
    P("space_control.unsuspended", gettext_noop("Space unblocked by the platform operator"), ("read_only",)),
    P("space_control.read_only_enabled", gettext_noop("Space put in read-only mode"), ("source",)),
    P("space_control.read_only_lifted", gettext_noop("Read-only mode ended"), ("source",)),
    P("space_control.schedule_set", gettext_noop("Archive and purge scheduled"), ("archive_on", "purge_due_at", "purge_grace_days")),
    P("space_control.schedule_cancelled", gettext_noop("Scheduled archive or purge cancelled")),
    P("space_control.schedule_blocked", gettext_noop("Scheduled archive or purge held"), ("reason_code",)),
    P("space_control.schedule_cleared", gettext_noop("Scheduled purge cleared"), ("reason_code",)),
    P("space_control.scheduled_archive_ran", gettext_noop("Space archived as scheduled"), ("purge_due_at",)),
    P("space_control.scheduled_purge_ran", gettext_noop("Space purged as scheduled"), ("makerspace_id", "slug")),
    P("space_control.ownership_invited", gettext_noop("New Space Manager invited (ownership transfer)"), ("invitation_id",)),
    P("space_control.ownership_transferred", gettext_noop("Space ownership transferred"),
      ("new_user_id", "previous_user_id", "previous_outcome")),
    P("space_control.space_onboarded", gettext_noop("Space created from a hosting request"), ("hosting_request_id", "manager_invited")),
    P("space_control.superadmin_bypass", gettext_noop("Superadmin acted in a paused or read-only space"),
      ("bypass_space_control", "path")),
    P("space_control.announcement_created", gettext_noop("Platform announcement created"),
      ("severity", "audience", "space_count", "send_email", "show_to_members")),
    P("space_control.announcement_cancelled", gettext_noop("Platform announcement cancelled")),
    P("space_control.announcement_emailed", gettext_noop("Platform announcement emailed"), ("recipient_count",)),
    P("managed_hosting.hosting_switch_changed", gettext_noop("Hosting other makerspaces switched"), ("from", "to")),
    P("managed_hosting.throttle_rate_changed", gettext_noop("Request rate limit changed"), ("scope", "from", "to")),
    P("managed_hosting.limit_defaults_changed", gettext_noop("Platform default limits changed"), ("changed", "from", "to")),
    P("managed_hosting.limit_threshold_crossed", gettext_noop("Limit warning sent"), ("key", "level", "percent")),
    P("space_control.limits_changed", gettext_noop("Space limits changed"), ("changed", "overrides")),
    P("platform_credential_limit.reached", gettext_noop("Platform credential allowance reached"), ("key", "period")),
    P("managed_hosting.hosting_type_changed", gettext_noop("Hosting type changed (own or hosted space)"),
      ("from", "to", "reason")),
    P("managed_hosting.plan_created", gettext_noop("Hosting plan created"), ("fields",)),
    P("managed_hosting.plan_updated", gettext_noop("Hosting plan changed"), ("fields",)),
    P("managed_hosting.plan_assigned", gettext_noop("Hosting plan assigned"), ("plan_id", "trial_days")),
    P("managed_hosting.plan_removed", gettext_noop("Hosting plan removed")),
    P("managed_hosting.trial_expired", gettext_noop("Hosting trial ended"), ("plan_id",)),
    P("managed_hosting.invoice_created", gettext_noop("Hosting invoice recorded"), ("amount_minor", "currency", "due_on")),
    P("managed_hosting.invoice_paid", gettext_noop("Hosting invoice paid"), ("method", "amount_minor")),
    P("managed_hosting.invoice_voided", gettext_noop("Hosting invoice voided")),
    P("managed_hosting.billing_settings_updated", gettext_noop("Hosting billing settings changed"), ("fields",)),
)
