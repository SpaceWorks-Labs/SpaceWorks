"""Route classes for r2-superadmin-controls (#185, #187A). Authority stays in each view.

* Platform-only: the superadmin console's space controls, onboarding, announcements and
  managed-hosting administration.
* Membership-only: a space's own hosting plan usage and invoices (its Space Manager, or
  the superadmin through the console surface rule).
* Shared: the signed-in notices feed (banners and the paused page) for every account.
"""

PLATFORM_ONLY_ROUTES = frozenset("""
admin-platform-space-health admin-platform-space-health-detail
admin-space-suspend admin-space-unsuspend admin-space-read-only admin-space-read-only-lift
admin-space-schedule admin-space-schedule-cancel admin-space-archive admin-space-unarchive admin-space-purge
admin-space-transfer-ownership admin-platform-hosting-requests admin-platform-hosting-request
admin-platform-hosting-request-approve admin-platform-hosting-request-changes admin-platform-hosting-request-reject
admin-platform-announcements admin-platform-announcement admin-platform-announcement-cancel
admin-platform-hosting-plans admin-platform-hosting-plan admin-space-plan admin-platform-hosting-invoices
admin-platform-hosting-invoice-payment admin-platform-hosting-invoice-void admin-platform-hosting-billing-settings
""".split())

MEMBERSHIP_ROUTES = frozenset("""
admin-makerspace-hosting-plan admin-makerspace-hosting-invoices admin-makerspace-hosting-invoice-checkout
""".split())

SHARED_ROUTES = frozenset({"platform-notices"})
