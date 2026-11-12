"""Reviewed staff-route names, grouped by authority source (V8).

A classification opens no permission. Mixed-method routes retain each method's
existing action check. Names are explicit so a new URL cannot inherit authority.
"""

MEMBERSHIP_ROUTES = frozenset("""
backup-recovery-state
admin-backup-archive-rehydrate admin-backup-destination admin-backup-destination-probe
admin-backup-download-url admin-makerspace-backups
admin-backup-destination-push admin-backup-destination-retire admin-backup-destination-uploads
admin-backup-destinations admin-certification-grant-renew admin-certification-grant-revoke
admin-certification-members admin-certification-type-detail admin-certification-type-grants
admin-certification-types admin-deployment-backups admin-device-detail
admin-device-enrollment-create admin-device-list admin-device-revoke admin-kiosk-station-detail
admin-kiosk-station-list-create admin-kiosk-station-reveal admin-kiosk-station-rotate
admin-label-command-list admin-machine-consumable-candidates admin-machine-consumable-detail
admin-machine-consumables admin-machine-consumption-log admin-machine-detail
admin-machine-document-detail admin-machine-document-presign admin-machine-document-url
admin-machine-documents admin-machine-error-logs admin-machine-image
admin-machine-operator-candidates admin-machine-operator-detail admin-machine-operators
admin-machine-publicity admin-machine-retire admin-machine-service-file-detail
admin-machine-service-file-finalize admin-machine-service-file-presign
admin-machine-service-file-url admin-machine-service-payment-mark-offline
admin-machine-service-payment-waive admin-machine-service-printer-pool-adjustments
admin-machine-service-printer-pool-detail admin-machine-service-printer-pools
admin-machine-service-printer-typed-manual-usage admin-machine-service-report
admin-machine-service-request-accept admin-machine-service-request-complete
admin-machine-service-request-fail admin-machine-service-request-reject
admin-machine-service-request-reprint admin-machine-service-request-start admin-machine-set-status
admin-machine-service-request-cancel
admin-machine-type-detail admin-machine-type-policy admin-machine-type-pricing
admin-machine-type-pricing-detail admin-machine-types admin-machine-unretire admin-machine-usage
admin-machine-warranty admin-machines admin-maintenance-log-document-detail
admin-maintenance-log-document-finalize admin-maintenance-log-document-presign
admin-maintenance-log-document-url admin-maintenance-log-list-create admin-maintenance-overdue
admin-maintenance-schedule-deactivate admin-maintenance-schedule-detail
admin-maintenance-schedule-list-create admin-makerspace-machine-service-report
admin-makerspace-provision-subdomain admin-membership-machine-scope admin-membership-revoke
admin-module-groups admin-module-install admin-module-uninstall admin-platform-backup-settings
admin-platform-dashboard admin-platform-email-settings admin-platform-payment-settings
admin-platform-problems admin-platform-social-auth-settings admin-printer-binding-detail
admin-printer-binding-list admin-printer-job-apply admin-printer-job-detail admin-printer-job-list
admin-restore-decision admin-restore-operation admin-restore-operations admin-space-pack-profiles
admin-staff-invitation-resend admin-staff-invitation-revoke admin-staff-invitations
admin-user-reset-password admin-users-booking-managers admin-users-event-managers
admin-users-handover admin-users-inventory-managers admin-users-machine-managers
admin-users-space-managers auth-claim-redeem auth-email-verification-confirm
auth-email-verification-resend auth-forgot-password auth-login auth-member-sign-up
auth-phone-link-confirm auth-phone-link-start auth-phone-login-confirm auth-phone-login-start
auth-phone-unlink auth-reset-password device-attestation-challenge device-login device-refresh
machine-material-detail machine-materials machine-type-intake maintenance-feed
maintenance-feed-calendar notifications-list notifications-read notifications-read-all
notifications-unread-count operations-dashboard social-apple social-github-browser-callback
social-github-browser-start social-github-link-start social-google social-link-callback social-nonce
social-oidc social-oidc-browser-callback social-oidc-browser-start social-oidc-link-start
social-provider-detail social-providers
tenant-migration-deployment-identity tenant-migration-disclosure-approvals
tenant-migration-disclosure-closure tenant-migration-disclosure-revoke
tenant-migration-export-detail tenant-migration-export-download-url tenant-migration-exports
tenant-migration-import-archive-chunk tenant-migration-import-archive-complete
tenant-migration-import-decisions tenant-migration-import-detail tenant-migration-import-run
tenant-migration-import-upload-start tenant-migration-import-verification tenant-migration-imports
tenant-migration-pairings tenant-migration-source-archive tenant-migration-source-quiesce
tenant-migration-source-recover tenant-migration-target-abort tenant-migration-target-activate
user-restore-access user-restrict
""".split())

DELEGABLE_ROUTES = frozenset("""
kiosk-station-operator-lease kiosk-station-work-package kiosk-station-evidence-prepare
kiosk-station-command-online payment-document-download
accepted-requests accountability-dashboard active-loans admin-accessible-booking-spaces
admin-accessible-events admin-api-client admin-api-client-rotate-secret admin-api-client-scopes
admin-api-clients admin-api-key-requests admin-api-settings
admin-asset-warranty admin-audit-logs admin-audit-verification-detail admin-audit-verifications
admin-bookable-space-booking-rules admin-bookable-space-clone
admin-bookable-space-deactivate admin-bookable-space-detail admin-bookable-space-image-delete
admin-bookable-space-image-finalize admin-bookable-space-image-presign
admin-bookable-space-list-create admin-bookable-space-photo admin-bookable-space-photo-order
admin-bookable-space-photo-presign admin-bookable-space-photos admin-booking-approve
admin-booking-arrival-confirm admin-booking-arrival-depart admin-booking-arrival-resolve
admin-booking-arrival-reverse admin-booking-broadcast-cancel admin-booking-broadcast-queue
admin-booking-broadcasts admin-booking-cancel admin-booking-complete admin-booking-details-edit
admin-booking-issue-resolve admin-booking-issues admin-booking-machine-types admin-booking-no-show
admin-booking-pass admin-booking-pass-preview admin-booking-pass-template admin-booking-reject
admin-booking-restore admin-booking-staff-grant-detail admin-booking-staff-grant-revoke
admin-booking-staff-grants admin-booking-staff-invite-revoke admin-booking-staff-invites
admin-booking-time-edit admin-booking-website admin-booking-website-asset
admin-booking-website-assets admin-booking-website-release admin-categories admin-category-detail
admin-email-log-retry admin-email-logs admin-email-template-detail admin-email-template-preview
admin-email-template-reset admin-email-templates admin-event-audience-organizations
admin-event-badge-template admin-event-badges-pdf admin-event-broadcast-cancel
admin-event-broadcast-queue admin-event-broadcasts admin-event-bulk-invites admin-event-cancel
admin-event-categories admin-event-category-detail admin-event-certificate-artwork admin-event-certificate-artwork-by-resource
admin-event-certificate-artwork-finalize admin-event-certificate-artwork-presign
admin-event-certificate-download admin-event-certificate-preview admin-event-certificate-reissue
admin-event-certificate-revoke admin-event-certificate-template admin-event-check-in-offline-roster
admin-event-check-in-offline-sync admin-event-check-in-resolve admin-event-check-in-station
admin-event-check-in-station-reveal admin-event-check-in-station-rotate admin-event-check-ins
admin-event-collaboration-inbox admin-event-collaboration-remove admin-event-collaboration-respond
admin-event-collaborators admin-event-complete admin-event-detail admin-event-duplicate
admin-event-eligible-members admin-event-feedback-responses admin-event-feedback-survey
admin-event-feedback-survey-close admin-event-feedback-survey-open admin-event-feedback-template
admin-event-image admin-event-invite-revoke admin-event-invites admin-event-list-create
admin-event-organizers admin-event-partner-makerspaces admin-event-promo-revoke admin-event-promos
admin-event-publish admin-event-registration-answers admin-event-registration-approve
admin-event-registration-cancel admin-event-registration-correct-attendance
admin-event-registration-list admin-event-registration-mark-attended
admin-event-registration-promote admin-event-registration-reject admin-event-registration-restore
admin-event-series-cancel admin-event-series-collaboration-inbox
admin-event-series-collaboration-remove admin-event-series-collaboration-respond
admin-event-series-collaborators admin-event-series-complete admin-event-series-detail
admin-event-series-extend admin-event-series-image admin-event-series-list-create
admin-event-series-occurrences admin-event-series-publish admin-event-series-invites
admin-event-series-invite-revoke admin-event-speaker-candidates
admin-event-speaker-invite admin-event-speaker-remove admin-event-speakers
admin-event-staff-grant-detail admin-event-staff-grant-revoke admin-event-staff-grants
admin-event-staff-invite-revoke admin-event-staff-invites admin-event-ticket-detail
admin-event-tickets admin-event-website-asset-detail admin-event-website-assets
admin-event-website-content admin-event-website-delay admin-event-website-release admin-inventory
admin-inventory-adjust-quantity admin-inventory-asset-detail admin-inventory-asset-fix-status
admin-inventory-asset-qr-history admin-inventory-assets admin-inventory-chain-of-custody
admin-inventory-detail admin-inventory-export admin-inventory-image admin-inventory-lending-history
admin-inventory-qr-history admin-invitation-request-decline admin-invitation-request-invite
admin-invitation-requests admin-kiosk-replay-detail admin-kiosk-replay-list
admin-kiosk-replay-resolve admin-machine-service-request-collect
admin-machine-service-request-detail admin-machine-service-request-list-create
admin-machine-type-email-template-detail admin-machine-type-email-template-reset admin-makerspace
admin-makerspace-archive-request-withdraw admin-makerspace-archive-requests
admin-makerspace-backup-status admin-makerspace-booking-queue
admin-makerspace-cover admin-makerspace-domain-settings
admin-settings-authority-grants admin-settings-authority-locks admin-settings-authority-effective
admin-makerspace-hosting-invitation-cancel admin-makerspace-hosting-invitations admin-makerspace-logo
admin-makerspace-payment-connect-onboard admin-makerspace-payment-settings admin-makerspace-profile
admin-makerspace-setup-state admin-makerspace-subdomain-request admin-makerspace-usage
admin-makerspace-waiver admin-makerspace-warranties admin-makerspaces admin-member-card-issue
admin-member-card-print admin-member-card-reissue admin-member-card-resolve admin-member-card-revoke
admin-member-card-template admin-member-cards admin-member-cards-sheet
admin-member-claim-code-list-create admin-member-claim-code-revoke admin-member-event-history
admin-membership-admission admin-membership-capabilities admin-membership-invitations
admin-membership-list-create admin-membership-plan-detail admin-membership-plans
admin-membership-request-approve admin-membership-request-revoke admin-membership-requests
admin-membership-revoke-m2 admin-membership-role-assign admin-membership-role-m2
admin-membership-term-cancel admin-membership-terms admin-membership-unverify
admin-membership-verify admin-membership-waiver-witness admin-memberships-roster
admin-needs-fix-action admin-needs-fix-shelf admin-notification-destination-detail
admin-notification-destinations admin-notification-recipient-rules admin-notification-recipients
admin-notification-rules admin-organization-detail admin-organization-directory
admin-organization-hosting-invitation-cancel admin-organization-hosting-invitations
admin-organization-invitation-revoke admin-organization-invitations admin-organization-link-delete
admin-organization-email-sender admin-organization-links admin-organization-list
admin-organization-membership-detail
admin-organization-review admin-organization-review-queue admin-organization-resubmit
admin-organization-member-rollup
admin-organization-memberships admin-organized-event-attendance admin-organized-event-list admin-presence-check-in-guests admin-presence-end admin-presence-privacy admin-presence-related
admin-presence-displays admin-presence-display-detail admin-presence-display-link admin-presence-display-rotate
admin-presence-display-players admin-anthias-players admin-anthias-player admin-anthias-player-test
admin-anthias-player-sync admin-presence-now-config
admin-presence-sessions-current admin-presence-start admin-recurring-bookings admin-reorder-draft
admin-reorder-suggestions admin-return-policy admin-role-list-create admin-saved-view-detail
admin-saved-views admin-search admin-series-staff-grants admin-series-staff-invites
admin-series-website-asset-detail admin-series-website-assets admin-series-website-content
admin-series-website-delay admin-series-website-release admin-space-booking-eligible-members
admin-space-booking-list admin-space-pack admin-walk-in-member-create admin-warranty-document-detail
admin-warranty-document-presign admin-warranty-document-url admin-warranty-documents
analytics-active-loans analytics-aggregate analytics-booking-utilization analytics-damaged-lost
analytics-damaged-missing analytics-event-attendance analytics-fablab-health analytics-generic
analytics-machine-usage analytics-maintenance-activity analytics-member-activity analytics-most-lent
analytics-payment-reconciliation analytics-qr-scans analytics-recently-added analytics-returns
analytics-summary analytics-taken-items analytics-top-borrowers asset-generate asset-qr
auth-organization-invitation-redeem auth-organizations-self-service
booking-staff-invite-redeem broadcast-create container-contents container-detail container-history
container-move containers contract-channel contract-channels contract-test data-export-detail
data-export-download-url data-export-list-create delivery-log-list delivery-log-retry delivery-test
direct-loan-members direct-loan-return direct-loans email-suppression-delete email-suppression-list
event-staff-invite-redeem evidence-detail evidence-retention-policy evidence-retention-preview
evidence-upload-url guest-admin-active-loans guest-admin-request-return inventory-import-apply
inventory-import-job-detail inventory-import-jobs inventory-import-preview
inventory-import-sheet ledger ledger-aggregate
ledger-export ledger-export-aggregate makerspace-integration-health makerspace-verify-domain
notification-discord-install notification-mattermost-install notification-slack-install
notification-timing-policy organization-analytics payment-billing-settings payment-deposit-release
payment-reconciliation-bulk-mark-offline payment-reconciliation-bulk-waive
payment-reconciliation-list payment-reconciliation-mark-offline payment-reconciliation-refund
payment-reconciliation-refund-offline payment-reconciliation-waive payment-refund-amend
payment-settlement-amend pending-requests problem-report-list problem-report-resolve problem-report-triage qr-boxes
qr-containers qr-print qr-print-batch-detail qr-print-batch-download qr-print-batch-items
qr-print-batches qr-rebind-target qr-resolve qr-revoke qr-scan qr-tools qr-external-assign report-catalog
report-catalog-aggregate report-export report-export-aggregate report-schedule-detail
report-schedule-run-now report-schedules request-accept request-assign-box request-history
request-issue request-reject request-return request-return-due request-timeline
saved-report-view-detail saved-report-views staff-kit-preview staff-loan-renew
staff-payment-document-url staff-payment-documents stock-transfer-detail stock-transfers
stocktake-apply-adjustments stocktake-approve stocktake-complete stocktake-count-lines
stocktake-detail stocktake-policy stocktake-resolve-scan stocktake-schedule-detail
stocktake-schedules stocktakes telegram-test-alert tenant-bootstrap to-buy-detail to-buy-export
to-buy-list to-buy-machine-type-options to-buy-move-to-inventory to-buy-move-to-printing
to-buy-receipt-detail to-buy-receipt-list to-buy-receipt-presign to-buy-receipt-url website-origins
whatsapp-twilio-template-refresh
""".split())

SHARED_ROUTES = frozenset("""
auth-change-password auth-logout auth-me auth-mfa auth-mfa-confirm auth-mfa-disable auth-mfa-enroll
auth-mfa-recovery auth-mfa-verify auth-reauth auth-reauth-enrollment-confirm
auth-reauth-enrollment-email auth-reauth-social-complete auth-reauth-social-start auth-refresh
contract-deliveries contract-endpoint-revoke contract-endpoint-start contract-endpoint-verify
contract-endpoints contract-preferences device-grant-detail device-grants device-logout inbox-count inbox-families
inbox-list inbox-read inbox-read-all inbox-snooze inbox-archive inbox-restore browser-alert-key
browser-alert-subscriptions live member-account-profile member-account-session-detail
member-account-sessions member-preferences push-device-detail push-device-list-create
""".split())

# These are account-kind boundaries, rather than sources of staff authority.
MEMBER_ROUTES = frozenset("""
auth-account-deletion auth-account-restore-email auth-account-restore-phone
auth-account-restore-social-start auth-account-restore-social-complete
auth-reauth-phone-start auth-reauth-phone-confirm auth-reauth-social-factor
""".split())

PLATFORM_ONLY_ROUTES = frozenset("""
admin-platform-mobile-readiness platform-analytics platform-analytics-makerspaces
platform-tenant-report-catalog platform-tenant-analytics platform-tenant-dashboard
platform-tenant-report-export
admin-makerspace-restores admin-space-restore admin-space-restore-confirm admin-space-restore-abort
admin-backup-schedule
""".split())

TENANT_STAFF_ROUTES = frozenset("""
messaging-settings messaging-test whatsapp-template-list whatsapp-template-detail
whatsapp-template-catalog admin-machine-usage-candidates
""".split())

# Compatibility ingress keeps its provider signatures, even while sends are held.
# It never accepts a browser, member, staff or API-client credential as authority.
SIGNED_PROTOCOL_ROUTES = frozenset("""
messaging-twilio-platform-status messaging-twilio-platform-inbound
messaging-twilio-status messaging-twilio-inbound messaging-meta-platform messaging-meta
""".split())

SHARED_ROUTES |= {"auth-logout-all", "member-messaging", "member-messaging-consent"}
# Release 2 U-A2: a person's device session asks for a staff step-up grant (Q12).
SHARED_ROUTES |= {"device-staff-grant"}
SHARED_ROUTES |= {"device-event-grant"}  # #173 (L21b): the native event-role step-up.
# Refund cases follow each charge's subject authority, like the reconciliation routes.
MEMBERSHIP_ROUTES |= {"refund-case-list", "refund-case-detail", "refund-case-approve", "refund-case-decline",
                      "refund-policy-list", "refund-policy-detail", "refund-policy-plan"}

# Release 2 L1, the public event surface: event-authority and space-settings routes.
DELEGABLE_ROUTES |= {
    "admin-event-short-link", "admin-event-short-link-regenerate", "admin-event-host-options",
    "admin-event-embed-policy", "admin-event-report-switches", "admin-makerspace-public-closed-notice",
}

# Release 2, one account per person: names fixed up front by U-A1 so U-B (staff roles),
# S-A (MFA reset) and U-C (account merge) classify nothing themselves.
STAFF_ROLE_ROUTES = frozenset({
    "admin-staff-roles", "admin-staff-roles-detail", "admin-staff-roles-revoke",
    "admin-staff-roles-restore", "admin-staff-roles-mfa-reset", "admin-staff-roles-bulk-invite",
})
# U-B: a person redeems their own staff invitation (signed in, before any staff role).
MEMBER_ROUTES |= {"auth-staff-invitation-accept"}
# Decision 305c: a signed-in reader opens a profile by account id (member-level; the view re-checks the audience).
MEMBER_ROUTES |= {"profile-by-account"}
ACCOUNT_MERGE_ROUTES = frozenset({
    "auth-account-merge-start", "auth-account-merge-prove", "auth-account-merge-resend",
    "auth-account-merge-preview", "auth-account-merge-confirm", "auth-account-merge-cancel",
    "auth-account-merge-passkey-options",  # GAP2 M6 (#65): passkey merge proof
})

# Release 2 lanes L4, L5, L15, L10/L11, L12 and L26 live in delegated_route_catalog_r2.py.
from .delegated_route_catalog_r2 import (  # noqa: E402
    DELEGABLE_ROUTES as _R2_DELEGABLE_ROUTES, MEMBERSHIP_ROUTES as _R2_MEMBERSHIP_ROUTES,
)
MEMBERSHIP_ROUTES |= _R2_MEMBERSHIP_ROUTES
DELEGABLE_ROUTES |= _R2_DELEGABLE_ROUTES
from .delegated_route_catalog_r2 import PLATFORM_ONLY_ROUTES as _R2_PLATFORM_ONLY_ROUTES  # noqa: E402
PLATFORM_ONLY_ROUTES |= _R2_PLATFORM_ONLY_ROUTES
from .delegated_route_catalog_superadmin import (  # noqa: E402  (#185, #187A, #190)
    DELEGABLE_ROUTES as _SA_DELEGABLE, MEMBERSHIP_ROUTES as _SA_MEMBERSHIP, PLATFORM_ONLY_ROUTES as _SA_PLATFORM_ONLY,
    SHARED_ROUTES as _SA_SHARED,
)
DELEGABLE_ROUTES |= _SA_DELEGABLE
PLATFORM_ONLY_ROUTES |= _SA_PLATFORM_ONLY
MEMBERSHIP_ROUTES |= _SA_MEMBERSHIP
SHARED_ROUTES |= _SA_SHARED
