"""Route classes for r2-superadmin-controls (#185, #187A). Authority stays in each view.

* Platform-only: the superadmin console's space controls, onboarding, announcements and
  managed-hosting administration; and the #190 parity paths (IP rules and blocks, account
  disable and two-step reset, OIDC providers, restore drills, self-host moves, platform
  provider credentials) that were /control/-only.
* Membership-only: a space's own hosting plan usage and invoices (its Space Manager, or
  the superadmin through the console surface rule).
* Shared: the signed-in notices feed (banners and the paused page) for every account.
* Delegable: a space's own chat templates, by its per-makerspace action (MANAGE_MAKERSPACE).
"""

PLATFORM_ONLY_ROUTES = frozenset("""
admin-platform-space-health admin-platform-space-health-detail
admin-space-suspend admin-space-unsuspend admin-space-read-only admin-space-read-only-lift
admin-space-schedule admin-space-schedule-cancel admin-space-archive admin-space-unarchive admin-space-purge
admin-space-transfer-ownership admin-platform-hosting-requests admin-platform-hosting-request
admin-platform-hosting-request-approve admin-platform-hosting-request-changes admin-platform-hosting-request-reject
admin-platform-announcements admin-platform-announcement admin-platform-announcement-cancel
admin-platform-hosting-plans admin-platform-hosting-plan admin-space-plan admin-platform-space-plan-bulk admin-platform-hosting-invoices
admin-platform-hosting-invoice-payment admin-platform-hosting-invoice-void admin-platform-hosting-billing-settings admin-platform-hosting-switch admin-space-limits admin-platform-space-limits-bulk admin-space-hosting-type admin-platform-request-limits admin-platform-request-limit admin-platform-limit-defaults
admin-platform-ip-rules admin-platform-ip-rule admin-platform-ip-blocks admin-platform-ip-block-unblock
admin-platform-restore-drills admin-platform-restore-drill-settings
admin-platform-accounts admin-platform-account-disable admin-platform-account-enable
admin-platform-account-reset-two-step admin-platform-oidc-providers admin-platform-oidc-provider
admin-platform-archive-requests admin-platform-archive-request-approve admin-platform-archive-request-decline
admin-platform-api-key-requests admin-platform-api-key-request-approve admin-platform-api-key-request-reject
admin-platform-subdomain-requests admin-platform-subdomain-request-approve admin-platform-subdomain-request-reject
admin-platform-chat-templates admin-platform-chat-template
admin-platform-sms-settings admin-platform-sms-settings-test admin-platform-push-settings
admin-platform-firebase-web-settings
admin-platform-push-settings-test admin-platform-whatsapp-settings admin-platform-whatsapp-settings-test
admin-platform-attestation-settings admin-platform-login-methods admin-platform-native-apps admin-platform-native-app
admin-platform-space-keys admin-platform-space-key-rotate admin-platform-space-archive-key
admin-platform-space-capability-purge
admin-platform-selfhost-moves admin-platform-selfhost-move-approve admin-platform-selfhost-move-reject
admin-platform-selfhost-move-export admin-platform-selfhost-move-discard admin-platform-selfhost-move-download-url
""".split())

MEMBERSHIP_ROUTES = frozenset("""
admin-makerspace-hosting-plan admin-makerspace-hosting-invoices admin-makerspace-hosting-invoice-checkout
admin-makerspace-allowances admin-makerspace-limits
""".split())

SHARED_ROUTES = frozenset({"platform-notices"})

# r2-parity-followups (#190): a Space Manager's own chat templates, MANAGE_MAKERSPACE like the chat rooms.
DELEGABLE_ROUTES = frozenset({"admin-chat-templates", "admin-chat-template"})
