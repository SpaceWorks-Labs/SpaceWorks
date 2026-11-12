"""Release-2 lane route classifications (L4, L5, L15, L10/L11, L12, L26).

Split out of `delegated_route_catalog.py` when it crossed the 300-line ceiling; the catalog
unions both sets into its own MEMBERSHIP_ROUTES and DELEGABLE_ROUTES, so these routes keep
exactly the classes they had there.
"""

MEMBERSHIP_ROUTES = set()
DELEGABLE_ROUTES = set()

# Decision 319, machine access grants: each view checks the machine authority itself (Space Manager, or a
# Machine Manager inside their machine scope).
MEMBERSHIP_ROUTES |= {"admin-machine-access", "admin-machine-access-revoke", "admin-machine-access-candidates", "admin-machine-open-access"}
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
    "billing-collection-sheet", "billing-cash-handover",  # parity O-B3: record_payment, `billing.collection_sheet`
    "paid-claim-list", "paid-claim-confirm", "paid-claim-reject",
    "settlement-confirmations", "settlement-confirm", "settlement-reject",
    "capture-flag-list", "capture-flag-resolve", "dispute-list", "dispute-detail", "payment-pay-link",
    "finance-access", "finance-summary", "finance-entries", "finance-entry", "finance-entry-void",
    "finance-entry-receipt", "finance-receipt-upload", "finance-opening-balances", "finance-event",
    "finance-event-budget", "finance-event-linked",
    # Decision 241: grouped area views (finance, To-Buy, consumables, repairs, warranties);
    # each section re-checks its own list's authority, payouts stay session-only.
    "admin-area-overview",
    # Decision 242: the own-area Payments queue (subject-owner authority, no record_payment grant).
    "payment-area-queue", "payment-area-queue-summary", "payment-area-claims", "payment-area-claim-confirm",
    "payment-area-claim-reject", "payment-area-pay-link", "payment-area-reminder",
    # Decision 242: the "Waiting on me" counters, narrowed per action inside the view.
    "operations-attention", "operations-schedule",
    # Decision 242: member 360 (manage_members, rows narrowed per area) and the all-or-nothing bulk decisions
    # (each row re-checks the single route's authority).
    "admin-member-activity", "admin-member-included-hours", "admin-org-hours-bank", "admin-org-hours-bank-ledger", "admin-bulk-requests", "admin-bulk-bookings", "admin-bulk-event-registrations",
    "admin-bulk-refund-cases", "admin-machine-bookings",
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
# Decision 312: the Device Adapter API's staff routes (MANAGE_DEVICES + machine scope; each view re-checks).
MEMBERSHIP_ROUTES |= frozenset("""admin-adapter-list admin-adapter-detail admin-adapter-binding-create
admin-adapter-commands admin-adapter-events admin-adapter-binding-detail admin-adapter-binding-command
admin-adapter-poses admin-adapter-aim admin-adapter-jog admin-adapter-indicate admin-adapter-position
admin-adapter-watch-create admin-adapter-watch-detail admin-adapter-watch-snapshot admin-adapter-credentials
admin-adapter-credential-detail admin-adapter-job-create admin-adapter-binding-config
admin-adapter-webhook admin-adapter-webhook-rotate admin-adapter-webhook-deliveries admin-adapter-type-profile
admin-adapter-access-decisions admin-adapter-usage admin-adapter-artifacts admin-adapter-artifact-url
admin-adapter-detections admin-adapter-telemetry admin-adapter-log-bundle admin-adapter-config-versions
admin-shelf-coverage admin-shelf-show admin-shelf-clear admin-shelf-locations admin-shelf-checks
admin-shelf-check-detail""".split())
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
# B13: an organization admin READS their own organization's hours bank; the view re-checks governance.
DELEGABLE_ROUTES |= {"admin-organization-hours-bank", "admin-organization-hours-ledger"}
# Decision 242(g): an event's loans and guest passes, read-only for whoever manages THAT event (event grants included).
DELEGABLE_ROUTES |= {"admin-event-loans", "admin-event-guest-passes"}
# Release-2 lane L16: issues, repairs, technicians, service state and item/room maintenance.
# Per-makerspace staff authority only (the Technician actions are never organization-grantable);
# every service re-checks the area manager's action or the Technician's assignment/coverage.
MEMBERSHIP_ROUTES |= frozenset("""admin-issues admin-issue-photo-upload admin-my-repair-jobs admin-service-state
admin-technicians admin-technician-candidates admin-technician-defaults admin-subject-maintenance admin-my-maintenance admin-room-outages
admin-issue-detail admin-issue-triage admin-issue-reject admin-issue-assign admin-issue-unassign admin-issue-dispatch
admin-issue-start admin-issue-work-log admin-issue-parts admin-issue-quote admin-issue-approve admin-issue-payout
admin-issue-fix admin-issue-close admin-technician-detail admin-technician-opt-in-link admin-technician-consent
admin-subject-maintenance-detail admin-subject-maintenance-run admin-machine-maintenance-run""".split())
# Decision 216 item 7/18: a loan's damaged lines and their repair handoff (session-only write).
MEMBERSHIP_ROUTES |= {"admin-loan-repairs"}
# Decision 216 event conflicts: the read-only room outage impact preview (same gate as service state).
MEMBERSHIP_ROUTES |= {"admin-room-outage-impact"}
# Release-2 lane L3, ID cards: card designs, their designer resources and card jobs are reached
# by member-card staff, ID-programme managers (organisation branch) and event organisers alike,
# so they are delegable; every view re-checks the design's own authority (card_designs.authority)
# or the job's requester. Member-card routes stay a staff role in the target space.
DELEGABLE_ROUTES |= frozenset("""admin-card-design admin-card-design-templates admin-card-design-publish
admin-card-design-submit admin-card-design-approve admin-card-design-reject admin-card-design-reset
admin-card-design-export admin-card-design-import admin-card-design-preview admin-card-design-assets
admin-card-design-asset-finalize admin-card-design-asset admin-card-design-fonts admin-card-design-font-prepare
admin-card-design-font-file admin-card-job admin-card-job-cancel admin-card-job-result""".split())
# r2-idcards-best: version history and restore, the "Preview as" holder picker, the calibration
# sheet (design routes, re-checked by card_designs.authority) and the three sheet previews.
DELEGABLE_ROUTES |= frozenset("""admin-card-design-revisions admin-card-design-revision admin-card-design-restore
admin-card-design-holders admin-card-design-calibration admin-id-programme-card-job-preview
admin-event-card-job-preview""".split())
# Owner decision 219(h): archive/restore a card-design override and an ID programme (the views
# re-check card_designs.authority and the programme's MANAGE_ID_PROGRAMMES respectively).
DELEGABLE_ROUTES |= frozenset("""admin-card-design-archive admin-card-design-unarchive admin-id-programme-archive
admin-id-programme-unarchive""".split())
MEMBERSHIP_ROUTES |= frozenset({"admin-member-card-job-preview"})
# O-B4 (parity C21): the organisation default member-card design; the view re-checks MANAGE_MEMBER_CARDS in every owned space.
DELEGABLE_ROUTES |= frozenset({"admin-organization-member-card-design"})
# O-B4: titles list, numbering schemes (space routes), the staff verify panel (token only; the view re-checks
# SCAN_MEMBER_CARDS and answers a uniform 404) and desk print-face (a card id, like download).
MEMBERSHIP_ROUTES |= frozenset("""admin-card-design-titles admin-card-number-schemes admin-card-number-scheme-title
admin-member-card-print-face""".split())
DELEGABLE_ROUTES |= frozenset({"admin-card-verification-staff"})
# O-B4 part 2: staff ID cards. Space routes are membership-module routes; the id routes re-check
# `staff_card_services.can_manage` (MANAGE_MEMBER_CARDS or MANAGE_STAFF) and answer 404 otherwise.
MEMBERSHIP_ROUTES |= frozenset("""admin-staff-cards admin-staff-cards-bulk-issue admin-staff-card-settings
admin-staff-card-design admin-staff-card-jobs""".split())
DELEGABLE_ROUTES |= frozenset("""admin-staff-card admin-staff-card-reissue admin-staff-card-revoke
admin-staff-card-print-face admin-staff-card-download""".split())
# Card Studio (decision 314/315): saved templates. Every view re-checks template_access (card, programme or event
# management in the space) and, for design-bound steps, authority.can_edit.
DELEGABLE_ROUTES |= frozenset("""admin-card-templates admin-card-template-import admin-card-template
admin-card-template-duplicate admin-card-template-export admin-card-design-apply-template
admin-card-template-builtin""".split())
# CARD-STUDIO-2 (344(b)): library, brand kit, CSV merge (design routes; views re-check authority.require_edit).
DELEGABLE_ROUTES |= frozenset("""admin-card-design-asset-library admin-card-design-asset-library-delete
admin-card-design-brand-kit admin-card-design-csv-merge admin-card-design-barcode""".split())
MEMBERSHIP_ROUTES |= frozenset({"admin-staff-card-job-preview"})  # same space authority as admin-staff-card-jobs
# E-B1: the badge designer. Design routes re-check card_designs.authority; event routes the event's edit permission.
DELEGABLE_ROUTES |= frozenset("""admin-event-badge-designs admin-event-badge-design-role admin-card-design-badge-export
admin-card-design-badge-import admin-card-design-badge-convert
admin-event-badge-desk admin-event-badge-print-receipts""".split())
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
# Release-2 lane L6, paid ticketing v2: add-ons, sales rules, the order list, desk collection and
# the guest pay link are run by every organiser holding the event's registration grant (each view
# re-checks it). The refund override, venue fees and series pass prices are money policy: a staff
# role in the target space (`manage_events`) only.
DELEGABLE_ROUTES |= frozenset("""admin-event-addons admin-event-addon-detail admin-event-sales-settings
admin-event-orders admin-event-order-detail admin-event-registration-collect-payment
admin-event-registration-pay-link""".split())
MEMBERSHIP_ROUTES |= frozenset("""admin-event-refund-policy admin-event-venue-fee admin-event-venue-fee-charge
admin-event-series-pass-types admin-event-pass-type-detail""".split())
# Decision 223 G6: the read-only venue panel reaches co-organizers and delegates (publish_schedule,
# re-checked by event_authority); creating an event with a room step is tenant staff (manage_events).
DELEGABLE_ROUTES |= frozenset({"admin-event-venue"})
# Open items A22: the cross-event registration queue serves every holder of an event's registration
# grant too; the view keeps only the events `event_authority` lets the caller manage registrations on.
DELEGABLE_ROUTES |= frozenset({"admin-event-registration-queue"})
MEMBERSHIP_ROUTES |= frozenset({"admin-event-create-with-room", "admin-event-room-choices"})
# Release-2 lane L18, donations and sponsors: finance money of the space (view_finance, plus
# record_payment for every write), never delegated to an event or resource grant.
MEMBERSHIP_ROUTES |= frozenset("""admin-donations admin-donation-settings admin-donation-campaigns
admin-donation-campaign admin-donation-pledges admin-donation-pledge admin-donation-cancel admin-donation-return
admin-donation-tax-receipt admin-sponsors admin-sponsor-tiers admin-sponsor-tier admin-sponsor-perks
admin-sponsor-perk-fulfil admin-sponsor-charge-return admin-sponsor-event-link admin-sponsor admin-sponsor-archive
admin-sponsor-restore admin-sponsor-logo admin-sponsor-charges admin-sponsor-event-links
admin-sponsor-event-sponsors""".split())
# Decision 242(m): the Donations area -- same authority (manage_donations or view_finance; writes add
# manage_donations or record_payment), never delegated to an event or resource grant.
MEMBERSHIP_ROUTES |= frozenset("""admin-donation-donors admin-donation-export admin-donation-receipt-reissue
admin-donation-claim-confirm admin-donation-claim-reject""".split())
# Release-2 lane L22, the shop: its till, stock and money stay inside ONE space, so every route
# needs a staff role in the target space (the shop actions are never organization-grantable).
MEMBERSHIP_ROUTES |= frozenset("""admin-shop-settings admin-shop-products admin-shop-product admin-shop-product-image
admin-shop-variant admin-shop-variant-stock admin-shop-movements admin-shop-event-offers admin-shop-event-offer
admin-shop-orders admin-shop-order
admin-shop-order-ready admin-shop-order-move-pickup-to-space admin-shop-order-collect admin-shop-order-take-payment
admin-shop-order-cancel
admin-shop-order-returns admin-shop-order-receipt admin-shop-pos-quote admin-shop-pos-sale admin-shop-member-lookup
admin-shop-cash-sessions admin-shop-cash-session-close admin-shop-cash-session-confirm
admin-shop-report""".split())
# Release-2 lane L25 (#163B), Metabase analytics: opening dashboards needs view_analytics, which
# an organization grant may carry (delegable); the login, the secret and the dashboards list are
# the space's own Space Manager or the superadmin (membership-only); the platform connection is
# the superadmin's (platform-only). Every view re-checks its own authority (analytics.access).
DELEGABLE_ROUTES |= frozenset("""admin-makerspace-analytics admin-makerspace-analytics-embed""".split())
DELEGABLE_ROUTES |= frozenset({"admin-makerspace-telemetry"})
MEMBERSHIP_ROUTES |= frozenset("""admin-makerspace-analytics-connection admin-makerspace-analytics-login
admin-makerspace-analytics-login-rotate""".split())
PLATFORM_ONLY_ROUTES = frozenset("""admin-platform-analytics admin-platform-analytics-connection
admin-platform-analytics-login admin-platform-analytics-login-rotate admin-platform-analytics-embed""".split())
# Release-2 lane r2-platform-overview (#183A): the superadmin platform overview and its CSV.
PLATFORM_ONLY_ROUTES |= frozenset({"platform-overview", "platform-overview-export"})
PLATFORM_ONLY_ROUTES |= frozenset({"admin-platform-telemetry"})
# Decision 263, Grafana beside Metabase: viewing is delegable like the Metabase viewer routes,
# managing (connection, token, test, bundle) membership-only, the platform set platform-only.
DELEGABLE_ROUTES |= frozenset("""admin-makerspace-grafana admin-makerspace-grafana-embed
admin-makerspace-grafana-render""".split())
MEMBERSHIP_ROUTES |= frozenset("""admin-makerspace-grafana-connection admin-makerspace-grafana-token
admin-makerspace-grafana-test admin-makerspace-grafana-bundle""".split())
PLATFORM_ONLY_ROUTES |= frozenset("""admin-platform-grafana admin-platform-grafana-connection
admin-platform-grafana-token admin-platform-grafana-test admin-platform-grafana-bundle
admin-platform-grafana-embed admin-platform-grafana-render""".split())
# The superadmin insights page (G8) reads platform-wide aggregates behind require_platform; it was
# filed with the programme's membership-only routes, so no platform route list named it.
PLATFORM_ONLY_ROUTES |= frozenset({"admin-platform-insights"})
# Hack-money (#180 G13, #181 G7): the space's prize-tax proposal and accepted payee templates are
# the Space Manager's own finance settings, never delegated.
MEMBERSHIP_ROUTES |= frozenset({"admin-event-money-settings"})
# Decision 223, guest passes: the desk needs manage_members, the policy and products manage_makerspace;
# each view re-checks its own action and the `membership.guest_passes` / `membership.day_passes` switch.
MEMBERSHIP_ROUTES |= frozenset({
    "admin-guest-passes", "admin-guest-pass-sale", "admin-guest-pass-revoke", "admin-guest-pass-waiver",
    "admin-guest-pass-policy", "admin-day-pass-products", "admin-day-pass-product",
    "admin-day-pass-product-archive",
})
# Decision 223(k)/(l), wallet passes: the Space Manager's own signing credentials (manage_makerspace) and the
# desk's read-only guest-pass scan (manage_members); each view re-checks its action and the capability.
MEMBERSHIP_ROUTES |= frozenset({"admin-wallet-credentials", "admin-guest-pass-scan"})
# Release 0.12.0 lane L3b (decision 223 (k)): minors and guardian consent, volunteer hours and credits, and
# organization bookings. Each view re-checks its own action (manage_members, manage_makerspace for the policy
# and the consent text, manage_reservations for bookings) and its capability switch; none is delegable.
MEMBERSHIP_ROUTES |= frozenset("""admin-community-policy admin-minors admin-minor-clear admin-minor-consent-record
admin-guardian-consent-revoke admin-guardian-terms admin-volunteer-hours admin-volunteer-hours-import
admin-volunteer-hours-decide admin-volunteer-credits admin-volunteer-credit-void
admin-space-organization-booking admin-space-organization-booking-choices""".split())
# Parity O-B1, member units: each view re-checks its own action (view_member_units, manage_member_units,
# manage_members) and the `membership.units` / `membership.unit_scoped_staff` switch; none is delegable.
MEMBERSHIP_ROUTES |= frozenset("""admin-member-units admin-member-unit-levels admin-member-unit admin-member-unit-move
admin-member-unit-archive admin-member-unit-restore admin-membership-unit admin-staff-unit-scope admin-plan-units
admin-member-import-reviews admin-member-import-review-approve admin-member-import-review-reject""".split())
# Parity O-B2: bulk register actions and "ask for changes" re-check manage_members (+ manage_member_cards for the
# card actions), the unit scope and their own `membership.*` switch; neither is delegable.
MEMBERSHIP_ROUTES |= frozenset({"admin-member-register-bulk", "admin-membership-request-changes"})
# The platform credentials are the superadmin's alone (recent re-authentication on every write).
PLATFORM_ONLY_ROUTES |= frozenset({"admin-platform-wallet-credentials"})
# Decision 242(l): superadmin cross-space queues, snapshot, unread inbox and platform search (counts only).
PLATFORM_ONLY_ROUTES |= frozenset({"admin-platform-queues", "admin-platform-space-snapshot", "admin-platform-inbox",
                                    "admin-platform-search"})
# Open item C13: read-only module defaults and the platform admin list (superadmin only).
PLATFORM_ONLY_ROUTES |= frozenset({"admin-platform-module-defaults", "admin-platform-admins"})

# Release 0.12.0 lane L3a (decision 223): induction events, guest certifications and the incident
# register. Each view re-checks its own authority (machine-type certification authority, or the
# area-narrowed incident reach); none is delegable.
MEMBERSHIP_ROUTES |= frozenset("""admin-induction-events-upcoming admin-event-induction admin-event-induction-grant admin-event-induction-unlink
admin-guest-certification-revoke admin-incidents admin-incident-detail admin-incident-actions
admin-incident-action-detail admin-incident-assignees""".split())
# Open-items batch 2 (C25): upcoming events/bookings short of planned consumables. view_inventory plus a
# per-activity event/booking view re-check; not delegable.
MEMBERSHIP_ROUTES |= frozenset({"admin-consumable-planned-shortages"})
# Parity E-B8: webhook secret rotation, the own-SMTP test and a space's own privacy / terms text are the
# Space Manager's transport/settings authority (MANAGE_MAKERSPACE); the operator's legal pages are superadmin only.
MEMBERSHIP_ROUTES |= frozenset("""admin-notification-destination-rotate-secret admin-makerspace-email-test
admin-makerspace-legal-page""".split())
PLATFORM_ONLY_ROUTES |= frozenset({"admin-platform-legal-page"})

# Decision 314(c), the background-eraser adapter: provider settings are the Space Manager's own (manage_makerspace +
# `cards.photo_cutout`) or the superadmin's; cut-outs and the bulk photo upload re-check each card kind's own photo
# authority (member cards, staff cards, event organisers) and the same switch, so they are reachable like the
# single-photo routes.
MEMBERSHIP_ROUTES |= frozenset({"admin-image-adapter", "admin-image-adapter-test"})
PLATFORM_ONLY_ROUTES |= frozenset({"admin-platform-image-adapter", "admin-platform-image-adapter-test"})
DELEGABLE_ROUTES |= frozenset("""admin-member-card-photo-cutout admin-staff-card-photo-cutout
admin-event-id-card-photo-cutout admin-card-photo-batches admin-card-photo-batch admin-card-photo-batch-files
admin-card-photo-batch-item admin-card-photo-batch-apply""".split())
# Decision 342: machine use logged with an event. The set/clear route re-checks MANAGE_MACHINES and machine
# scope; the event-side routes re-check event authority (event grants included).
MEMBERSHIP_ROUTES |= {"admin-machine-use-event", "admin-machine-use-event-options"}
DELEGABLE_ROUTES |= {"admin-event-machine-use", "admin-event-machine-use-cost"}
# Decisions 341/343: per-type consumable profiles, the type-template catalogue and a job's consumables. Each view
# re-checks its own authority (the per-type settings rule, the Space Manager for templates, the job's machine scope).
MEMBERSHIP_ROUTES |= frozenset("""machine-type-consumables machine-type-consumable-detail machine-type-consumable-stock
machine-type-templates machine-type-template-detail machine-type-template-apply admin-machine-job-consumables
machine-type-setup machine-type-booking-defaults-apply machine-type-documents machine-type-document-presign
machine-type-document-detail""".split())
