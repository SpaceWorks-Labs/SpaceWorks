"""Release-2 lane route classifications (L4, L5, L15, L10/L11, L12, L26).

Split out of `delegated_route_catalog.py` when it crossed the 300-line ceiling; the catalog
unions both sets into its own MEMBERSHIP_ROUTES and DELEGABLE_ROUTES, so these routes keep
exactly the classes they had there.
"""

MEMBERSHIP_ROUTES = set()
DELEGABLE_ROUTES = set()

# Release 2 L4, the membership lifecycle: per-makerspace membership authority only.
# Each view keeps its own action check.
MEMBERSHIP_ROUTES |= {
    "admin-financial-year", "admin-membership-plan-archive", "admin-membership-titles",
    "admin-membership-title-detail", "admin-membership-invite-links", "admin-membership-invite-link-revoke",
    "admin-membership-renewal-worklist", "admin-membership-renewal-reminders",
    "admin-membership-join-requests-bulk-decide", "admin-member-import-preview", "admin-member-import-apply",
    "admin-member-imported", "admin-membership-erasure-requests", "admin-membership-erasure-approve",
    "admin-membership-erasure-reject", "admin-member-register", "admin-membership-summary",
    "admin-refund-case-membership-suggestion", "admin-membership-extend", "admin-membership-record",
    "admin-membership-title-assignments", "admin-membership-title-unassign", "admin-membership-consents",
    "admin-membership-history",
}
# Release 2 L5, money, tax and the finance ledger: each view re-checks its own action
# (view_finance, record_payment or the area manager's action through `finance_scope`).
MEMBERSHIP_ROUTES |= {
    "billing-tax", "billing-tax-gstin", "billing-tax-preview", "billing-tax-gstr1-json",
    "paid-claim-list", "paid-claim-confirm", "paid-claim-reject",
    "settlement-confirmations", "settlement-confirm", "settlement-reject",
    "capture-flag-list", "capture-flag-resolve", "dispute-list", "dispute-detail", "payment-pay-link",
    "finance-access", "finance-summary", "finance-entries", "finance-entry", "finance-entry-void",
    "finance-entry-receipt", "finance-receipt-upload", "finance-opening-balances", "finance-event",
    "finance-event-budget",
}

# Release 2 L15, pricing: each view re-checks its own authority -- the settings layer for
# rate cards, the item's own edit action for per-item prices, the Space Manager for
# discounts and the currency, return_request for loan charges and fee waivers.
MEMBERSHIP_ROUTES |= {
    "pricing-default", "pricing-impact", "pricing-currency", "pricing-rental-timing", "pricing-discounts",
    "pricing-discount", "pricing-discount-archive", "pricing-override", "loan-charges", "loan-fee-waivers",
    "loan-fee-waiver-revoke", "loan-accountability-charge",
}

# Release 2 L10/L11: machine-integration bindings (MANAGE_DEVICES + machine-type scope) and
# the Space Manager's self-host move request (MANAGE_MAKERSPACE). Each view keeps its check.
MEMBERSHIP_ROUTES |= {
    "admin-machine-type-integration-list", "admin-machine-type-integration-detail",
    "admin-machine-type-integration-status", "admin-makerspace-selfhost-move-request",
}
# Release-2 lane L12: loans, consumables and To-Buy (delegable); machine jobs, downtime and work orders
# keep their machine partition / per-subject checks. Every route re-checks its own action.
DELEGABLE_ROUTES |= frozenset("""admin-consumables admin-consumable-use to-buy-refill-consumable to-buy-mark-bought
procurement-vendors procurement-vendor-detail staff-request-cancel staff-loan-waitlist admin-loan-reservation-policy""".split())
MEMBERSHIP_ROUTES |= frozenset("""admin-machine-job-request-changes admin-machine-job-quote admin-machine-job-queue-now
admin-machine-job-reorder admin-machine-job-urgent admin-machine-job-assign admin-machine-job-uncollected
admin-machine-job-batch-start admin-machine-job-batch-complete admin-machine-job-board admin-machine-type-job-settings
admin-machine-downtime admin-machine-lockout admin-work-orders admin-work-order-status admin-work-order-assign""".split())
# Release-2 lane L23: metered machine sessions. Each view re-checks MANAGE_MACHINES and the
# actor's machine scope; the type setting goes through the settings-authority layer.
MEMBERSHIP_ROUTES |= frozenset("""admin-machine-sessions admin-machine-session-stop admin-machine-session-amend
admin-machine-session-assign admin-machine-session-confirm admin-machine-type-session-settings""".split())
# Release 2 L26 (#170): Settings › Public stats, a Space-Manager-only settings group.
DELEGABLE_ROUTES |= {"admin-makerspace-public-stats-settings"}
# Release-2 lane L16: issues, repairs, technicians, service state and item/room maintenance.
# Per-makerspace staff authority only (the Technician actions are never organization-grantable);
# every service re-checks the area manager's action or the Technician's assignment/coverage.
MEMBERSHIP_ROUTES |= frozenset("""admin-issues admin-issue-photo-upload admin-my-repair-jobs admin-service-state
admin-technicians admin-technician-candidates admin-technician-defaults admin-subject-maintenance admin-my-maintenance admin-room-outages
admin-issue-detail admin-issue-triage admin-issue-reject admin-issue-assign admin-issue-unassign admin-issue-dispatch
admin-issue-start admin-issue-work-log admin-issue-parts admin-issue-quote admin-issue-approve admin-issue-payout
admin-issue-fix admin-issue-close admin-technician-detail admin-technician-opt-in-link admin-technician-consent
admin-subject-maintenance-detail admin-subject-maintenance-run admin-machine-maintenance-run""".split())
# Release-2 lane L3, ID cards: card designs, their designer resources and card jobs are reached
# by member-card staff, ID-programme managers (organisation branch) and event organisers alike,
# so they are delegable; every view re-checks the design's own authority (card_designs.authority)
# or the job's requester. Member-card routes stay a staff role in the target space.
DELEGABLE_ROUTES |= frozenset("""admin-card-design admin-card-design-templates admin-card-design-publish
admin-card-design-submit admin-card-design-approve admin-card-design-reject admin-card-design-reset
admin-card-design-export admin-card-design-import admin-card-design-preview admin-card-design-assets
admin-card-design-asset-finalize admin-card-design-asset admin-card-design-fonts admin-card-design-font-prepare
admin-card-design-font-file admin-card-job admin-card-job-cancel admin-card-job-result""".split())
MEMBERSHIP_ROUTES |= frozenset("""admin-member-card-settings admin-card-designs admin-member-card-jobs
admin-member-card-download admin-member-card-email admin-member-card-photo-request admin-member-card-presence
admin-card-approval-levels admin-member-card-photo""".split())
# Release-2 lane L3, ID programmes and event cards: programme routes are reached by the host
# space's programme managers and by organisation governors (organisation branch); event card
# routes by every organiser of the event. Each view re-checks its own authority.
DELEGABLE_ROUTES |= frozenset("""admin-organization-id-programmes admin-id-programme admin-id-programme-design
admin-id-programme-approval admin-id-programme-cards admin-id-programme-decide admin-id-programme-import-preview
admin-id-programme-import admin-id-programme-card-jobs admin-id-programme-card admin-id-programme-card-download
admin-id-programme-card-email admin-id-programme-card-photo-request admin-event-card-designs
admin-event-card-settings admin-event-id-cards admin-event-id-card-extras admin-event-card-jobs
admin-event-card-scan admin-event-id-card admin-event-id-card-revoke admin-event-id-card-download
admin-id-programme-card-photo admin-event-id-card-photo""".split())
