"""Lane C registration inputs for G; none of these installs a registry entry."""
MODEL_MODULES = (
    "apps.events.contributions.models_roles", "apps.events.contributions.models_shifts",
    "apps.events.contributions.models_notices",
    "apps.events.contributions.models_policy", "apps.events.contributions.models_admission",
    "apps.events.mentoring.models_queue", "apps.events.mentoring.models_rounds",
    "apps.events.mentoring.models_operations",
)
PII_FIELDS = {
    "events.EventRoleAssignment": ("application_notes", "answers"),
    "events.EventContributionHoursEntry": ("reason",),
    "events.EventShiftAttendanceCorrection": ("reason",),
    "events.MentorProfile": ("affiliation",),
    "events.EventHelpRequest": ("summary",),
    "events.EventHelpAction": ("note",),
    "events.EventHelpComment": ("body",),
    "events.MentorRoundLock": ("overrides",),
    "events.MentorRoundCheckin": ("answers", "overrides"),
    "events.MentorConflict": ("reason",),
    "events.MentorImportPreview": ("mapping",),
    "events.OfficeHoursChange": ("reason",),
    "events.EventRoleAnswerRevision": ("answers", "reason"),
    "events.EventRequirementOverride": ("reason",),
}
# Each mapped model has a direct, non-null makerspace FK. No account-vault fields.
TENANT_EXCLUDED = (
    "events.EventGrantEntitlement", "events.MentorRoundLock", "events.MentorImportPreview",
    "events.MentorNotificationIntent",
    "events.EventContributorNotice",
    "events.MentorAttentionPreference",
)
APPEND_ONLY = (
    "events.EventContributionHoursEntry", "events.EventShiftAttendanceCorrection",
    "events.EventHelpAction", "events.EventHelpComment", "events.MentorRoundCheckin",
    "events.MentorNomination",
    "events.OfficeHoursChange",
    "events.EventRoleAnswerRevision", "events.EventRequirementOverride",
    "events.EventContributorAdmission", "events.MentorAssignmentRun",
)
ROUTE_MODULES = {
    "member": ("apps.events.contributions.urls_member", "apps.events.mentoring.urls_member"),
    "admin": ("apps.events.contributions.urls_admin", "apps.events.mentoring.urls_admin"),
    "public": ("apps.events.contributions.urls_public",),
}
TASKS = {
    "contributor_notice_sweep": "apps.events.contributions.notifications.sweep",
    "mentor_notification_sweep": "apps.events.mentoring.notifications.sweep",
    "mentor_help_attention": "apps.events.mentoring.notifications.escalate",
    "mentor_help_expiry": "apps.events.mentoring.help_expiry.expire",
}
AUTHORITY_ADAPTERS = {
    "active_entitlements": "apps.events.contributions.authority.active_entitlements",
    "grant_ids": "apps.events.contributions.authority.grant_ids",
    "permissions_for": "apps.events.contributions.authority.permissions_for",
    "subset_validator": "apps.events.contributions.authority.subset_validator",
    "sync_role_locked": "apps.events.contributions.sources.sync_role_locked",
    "sync_shift_locked": "apps.events.contributions.sources.sync_shift_locked",
    "resolve_role_subject": "apps.events.contributions.subjects.require_owner",
    "resume_eligibility_only": "apps.events.contributions.subjects.require_resume_eligible",
    "judging_conflict": "apps.events.mentoring.policy.is_conflicted",
    "readiness_summary": "apps.events.mentoring.analytics.summary",
    "contributor_admission": "apps.events.contributions.admission_adapter.admit",
    "verified_contribution_subject": "apps.events.contributions.certificate_subjects.resolve",
}

# Deliberately excluded from ROUTE_MODULES: G ratifies C2 contracts/fixtures,
# origin/claim/delegated/API-client lookups and OpenAPI before mounting these.
COMPLETION_ROUTE_PROPOSALS = {
    "admin": (("apps.events.contributions.urls_completion", "ADMIN"),
              ("apps.events.mentoring.urls_completion", "urlpatterns")),
    "member": (("apps.events.contributions.urls_completion", "MEMBER"),),
}
