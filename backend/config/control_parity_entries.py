"""The #190 parity rows; read through ``config.control_parity`` (see its docstring)."""

from config.control_parity import KEY_ROTATION, RAW_REPAIR, SERVER, host, web

PS = "Platform settings"  # /admin/platform?section=...
SP = "Platform → Spaces"  # /admin/platform-spaces
S = "Space console"       # /m/<space>/admin/<tab>, reached by the superadmin in every space (#115)
ARCH = ("admin-platform-archive-requests", "admin-platform-archive-request-approve")

ENTRIES = (
    # Overview and makerspaces
    ("space_controls.platformannouncement.cancel_announcements", web(f"{SP} → Announcements", "admin-platform-announcement-cancel")),
    ("makerspaces.makerspace", web(f"{SP}; {S} → Settings", "admin-makerspaces", "admin-makerspace")),
    ("makerspaces.makerspace.archive_makerspaces", web(f"{SP} → Manage → Archive", "admin-space-archive")),
    ("makerspaces.makerspace.unarchive_makerspaces", web(f"{SP} → Manage → Unarchive", "admin-space-unarchive")),
    ("makerspaces.makerspace.purge_makerspaces", web(f"{SP} → Manage → Purge", "admin-space-purge")),
    ("makerspaces.makerspace.suspend_makerspaces", web(f"{SP} → Manage → Suspend", "admin-space-suspend")),
    ("makerspaces.makerspace.unsuspend_makerspaces", web(f"{SP} → Manage → Unblock", "admin-space-unsuspend")),
    ("makerspaces.makerspace.read_only_makerspaces", web(f"{SP} → Manage → Read-only", "admin-space-read-only")),
    ("makerspaces.makerspace.lift_read_only_makerspaces", web(f"{SP} → Manage → Lift read-only", "admin-space-read-only-lift")),
    ("makerspaces.makerspace.cancel_makerspace_schedules", web(f"{SP} → Manage → Cancel schedule", "admin-space-schedule-cancel")),
    ("makerspaces.makerspace.approve_archive_requests", web(f"{PS} → Requests → Archive", *ARCH)),
    ("makerspaces.makerspace.decline_archive_requests", web(f"{PS} → Requests → Archive", "admin-platform-archive-request-decline")),
    ("makerspaces.makerspacearchiverequest", web(f"{PS} → Requests → Archive", *ARCH)),
    ("makerspaces.makerspacearchiverequest.approve_selected", web(f"{PS} → Requests → Archive", *ARCH)),
    ("makerspaces.makerspacearchiverequest.decline_selected", web(f"{PS} → Requests → Archive", "admin-platform-archive-request-decline")),
    ("makerspaces.subdomainrequest", web(f"{PS} → Requests → Web addresses", "admin-platform-subdomain-requests")),
    ("makerspaces.subdomainrequest.approve_and_provision", web(f"{PS} → Requests → Web addresses", "admin-platform-subdomain-request-approve")),
    ("makerspaces.subdomainrequest.reject_selected", web(f"{PS} → Requests → Web addresses", "admin-platform-subdomain-request-reject")),
    ("hosting_requests.hostingrequest.accept_selected", web(f"{SP} → Onboarding", "admin-platform-hosting-request-approve")),
    ("hosting_requests.hostingrequest.reject_selected", web(f"{SP} → Onboarding", "admin-platform-hosting-request-reject")),
    ("hosting_requests.hostingrequest.request_changes_selected", web(f"{SP} → Onboarding", "admin-platform-hosting-request-changes")),
    ("view:hosting_requests_hostingrequest_create_makerspace", web(f"{SP} → Onboarding → Approve (creates the space)",
                                                                   "admin-platform-hosting-request-approve")),
    ("view:makerspaces_makerspace_security", web(f"{S} → Security (locks)", "admin-makerspace-security-settings",
                                                 "admin-makerspace-security-lock")),
    ("view:makerspaces_makerspace_create_staff_account", web(f"{S} → Staff & roles → Invite", "admin-staff-invitations")),
    ("view:makerspaces_makerspace_keys", KEY_ROTATION),
    ("view:makerspaces_makerspace_capability_purge", host(f"Deleting a switched-off capability's data, with the key typed back: {SERVER}")),
    # Organizations
    ("organizations.organization", web("Organizations", "admin-organization-list", "admin-organization-detail")),
    ("organizations.organizationmakerspace", web("Organizations → Spaces", "admin-organization-links", "admin-organization-link-delete")),
    ("organizations.organizationmembership", web("Organizations → Members", "admin-organization-memberships",
                                                 "admin-organization-membership-detail")),
    # People & access
    ("accounts.user", web(f"{PS} → Accounts; {S} → Staff & roles, Members", "admin-platform-accounts", "admin-staff-roles",
                          "admin-staff-invitations")),
    ("accounts.user.disable_account", web(f"{PS} → Accounts → Disable", "admin-platform-account-disable")),
    ("accounts.user.enable_account", web(f"{PS} → Accounts → Re-enable", "admin-platform-account-enable")),
    ("accounts.user.reset_two_step", web(f"{PS} → Accounts → Reset two-step; {S} → Staff & roles",
                                         "admin-platform-account-reset-two-step", "admin-staff-roles-mfa-reset")),
    ("accounts.user.reset_password_selected", web(f"{S} → Staff & roles → Reset password", "admin-user-reset-password")),
    ("accounts.user.restrict_access", web(f"{S} → Members → Restrict", "user-restrict")),
    ("accounts.user.restore_access", web(f"{S} → Members → Restore", "user-restore-access")),
    ("view:accounts_user_pii_reveal", web(f"{S} → PII window banner", "admin-makerspace-pii-access")),
    ("accounts.platformpiiaccessgrant.close_own_windows", web(f"{S} → PII window banner → Close", "admin-makerspace-pii-access")),
    ("accounts.memberclaimcode", web(f"{S} → Members → Claim codes", "admin-member-claim-code-revoke")),
    ("makerspaces.makerspacemembership", web(f"{S} → Staff & roles", "admin-staff-roles-detail")),
    ("makerspaces.membershiprequest", web(f"{S} → Members → Requests", "admin-membership-requests",
                                          "admin-membership-request-approve")),
    ("makerspaces.membercard", web(f"{S} → Cards", "admin-member-cards")),
    ("makerspaces.makerspacewaiver", web(f"{S} → Settings → Waiver", "admin-makerspace-waiver")),
    ("makerspaces.pendingimportedmembership", web(f"{S} → Members → Imported", "admin-member-imported")),
    ("makerspaces.importeduserreconciliation", web("Platform → space moves → identity decisions", "tenant-migration-import-decisions")),
    ("makerspaces.memberprofile", host(f"Members edit their own profiles; correcting one by hand is raw record repair: {SERVER}")),
    ("makerspaces.memberproject", host(f"Members edit their own projects; correcting one by hand is raw record repair: {SERVER}")),
    ("presence.presencesession", web(f"{S} → Members → In the space → End", "admin-presence-end")),
    # Security
    ("accounts.ipaccessrule", web(f"{PS} → IP access", "admin-platform-ip-rules", "admin-platform-ip-rule")),
    ("accounts.ipautoblock.unblock_selected", web(f"{PS} → IP access → Lift now", "admin-platform-ip-block-unblock")),
    ("accounts.oidcprovider", web(f"{PS} → Single sign-on", "admin-platform-oidc-providers", "admin-platform-oidc-provider")),
    ("accounts.nativeappregistration", host(f"Mobile app identities are set once with the server's attestation setup: {SERVER}")),
    ("view:accounts_nativeappregistration_mobile_readiness", web(f"{PS} → Deployment (mobile readiness)", "admin-platform-mobile-readiness")),
    ("axes.accessattempt", host("Recovery command: manage.py axes_reset_username <name> (or the lockout lifts by itself)")),
    ("axes.accessattempt.cleanup_expired_attempts", host("Recovery command: manage.py axes_reset (expired lockouts also clear by themselves)")),
    ("axes.accessfailurelog", RAW_REPAIR),
    ("axes.accesslog", RAW_REPAIR),
)

from config.control_parity_entries_more import MORE_ENTRIES  # noqa: E402

ENTRIES = ENTRIES + MORE_ENTRIES
