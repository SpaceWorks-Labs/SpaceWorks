import { t } from "@lingui/core/macro";
export type FeatureDefinition = {
  key: string;
  // null => standalone feature with no parent-module prerequisite (always toggleable).
  parent_module: string | null;
  label: string;
};

// Mirrors `apps/makerspaces/capabilities.py::FEATURE_DEFINITIONS`. The backend test
// `tests/test_capabilities.py::test_frontend_feature_definitions_match_the_backend`
// parses this file and fails if the two drift, so keep the shape (one object literal
// per line, keys in this order) that the guard reads.
export const FEATURE_DEFINITIONS: readonly FeatureDefinition[] = [
  { key: "notifications.quiet_hours", parent_module: "notifications", label: t`Quiet hours` },
  { key: "notifications.digests", parent_module: "notifications", label: t`Daily notification digests` },
  { key: "membership.broadcasts", parent_module: "membership", label: t`Member broadcasts` },
  { key: "bookings.recurring", parent_module: "bookings", label: t`Recurring bookings` },
  { key: "loans.enabled", parent_module: "staff_admin", label: t`Hardware loans` },
  { key: "inventory.notify_when_back", parent_module: "public_inventory", label: t`Notify when back` },
  { key: "stocktake.discipline", parent_module: "stocktake", label: t`Stocktake discipline` },
  { key: "machines.public_detail", parent_module: "machines", label: t`Public machine details` },
  { key: "machines.material_catalogue", parent_module: "machines", label: t`Local material catalogue` },
  { key: "machines.structured_intake", parent_module: "machine_service", label: t`Structured machine intake` },
  { key: "maintenance.meters", parent_module: "machines", label: t`Usage-based maintenance` },
  { key: "maintenance.calendar_feed", parent_module: "machines", label: t`Maintenance calendar feed` },
  { key: "packs.import", parent_module: "staff_admin", label: t`Space packs` },
  { key: "membership.auto_renew", parent_module: "membership", label: t`Automatic membership renewal` },
  { key: "membership.lifecycle_mail", parent_module: "membership", label: t`Membership lifecycle mail` },
  { key: "membership.self_service", parent_module: "membership", label: t`Member account self-service` },
  { key: "membership.self_export", parent_module: "membership", label: t`Member data export` },
  { key: "reports.saved_views", parent_module: "reports", label: t`Saved report views` },
  { key: "billing.documents", parent_module: null, label: t`Receipt documents` },
  { key: "billing.reminders", parent_module: "notifications", label: t`Payment reminders` },
  { key: "loans.renewals", parent_module: "request_workflow", label: t`Loan renewals` },
  { key: "loans.limits", parent_module: "request_workflow", label: t`Borrow limits` },
  { key: "loans.kit_checklist", parent_module: "containers", label: t`Kit checklists` },
  { key: "staff.invitations", parent_module: null, label: t`Staff invitations` },
  { key: "ui.delight", parent_module: null, label: t`Interface effects` },
  { key: "ui.easter_eggs", parent_module: null, label: t`Easter eggs` },
  { key: "membership.vouching", parent_module: "membership", label: t`Membership vouching` },
  { key: "membership.application_form", parent_module: "membership", label: t`Membership application form` },
  { key: "payments.machines", parent_module: "machines", label: t`Machine payments` },
  { key: "payments.bookings", parent_module: "bookings", label: t`Booking payments` },
  { key: "payments.events", parent_module: "events", label: t`Event payments` },
  { key: "payments.membership", parent_module: "membership", label: t`Membership payments` },
  { key: "payments.loans", parent_module: "payments", label: t`Loan deposits and late fees` },
  { key: "charges.enabled", parent_module: null, label: t`Track money owed` },
  { key: "charges.bookings", parent_module: "bookings", label: t`Track booking charges` },
  { key: "charges.events", parent_module: "events", label: t`Track event charges` },
  { key: "charges.machines", parent_module: "machines", label: t`Track machine charges` },
  { key: "charges.membership", parent_module: "membership", label: t`Track membership charges` },
  { key: "charges.loans", parent_module: "request_workflow", label: t`Track loan charges` },
  { key: "inventory.self_checkout", parent_module: null, label: t`Self checkout` },
  { key: "inventory.contact_self_checkout", parent_module: null, label: t`Self checkout without an account` },
  { key: "payments.enabled", parent_module: "payments", label: t`Payments` },
  { key: "mobile.push", parent_module: "mobile", label: t`Native push` },
  { key: "presence.geofence", parent_module: null, label: t`Presence geofence` },
  { key: "notifications.delegated_recipients", parent_module: "machines", label: t`Delegated maintenance recipients` },
  { key: "notifications.member_inbox", parent_module: "notifications", label: t`Member inbox` },
  { key: "notifications.member_preferences", parent_module: "notifications", label: t`Member communication preferences` },
  { key: "events.invites", parent_module: "events", label: t`Event invitations` },
  { key: "events.account_registration", parent_module: "events", label: t`Account event registration` },
  { key: "events.organization_audience", parent_module: "events", label: t`Participating organizations audience` },
  { key: "bookings.broadcasts", parent_module: "bookings", label: t`Booker broadcasts` },
  { key: "events.broadcasts", parent_module: "events", label: t`Event broadcasts` },
  { key: "reports.event_pdf", parent_module: "reports", label: t`Post-event PDF` },
  { key: "reports.event_exports", parent_module: "reports", label: t`Event detail exports` },
  { key: "events.ticket_types", parent_module: "events", label: t`Event ticket types` },
  { key: "events.promo_codes", parent_module: "events", label: t`Event promo codes` },
  { key: "events.offline_checkin", parent_module: "events", label: t`Offline & station check-in` },
  { key: "events.hackathons", parent_module: "events", label: t`Hackathon programmes` },
  { key: "events.mentoring", parent_module: "events", label: t`Mentor desk` },
  { key: "events.mentor_rounds", parent_module: "events", label: t`Mentor check-in rounds` },
  { key: "events.volunteering", parent_module: "events", label: t`Volunteer contributions` },
  { key: "events.project_gallery", parent_module: "events", label: t`Project gallery` },
  { key: "events.pairwise_judging", parent_module: "events", label: t`Pairwise judging` },
  { key: "machines.certification_reminders", parent_module: "machines", label: t`Certification reminders` },
  { key: "maintenance.reminders", parent_module: "machines", label: t`Maintenance reminders` },
  { key: "machines.certifications", parent_module: "machines", label: t`Certification gating` },
  { key: "inventory.kiosk", parent_module: null, label: t`Kiosk` },
  { key: "bookings.passes", parent_module: "bookings", label: t`Printable booking passes` },
  { key: "bookings.clone", parent_module: "bookings", label: t`Clone resources` },
  { key: "bookings.staff_tools", parent_module: "bookings", label: t`Staff reservation tools` },
  { key: "bookings.analytics", parent_module: "bookings", label: t`Resource analytics` },
  { key: "bookings.utilization_pdf", parent_module: "bookings", label: t`Resource utilization PDF` },
  { key: "bookings.exports", parent_module: "bookings", label: t`Resource reservation exports` },
  { key: "bookings.confirmations", parent_module: "bookings", label: t`Private booking confirmations` },
  { key: "bookings.checkin", parent_module: "bookings", label: t`Booking QR arrival` },
  { key: "bookings.staff_grants", parent_module: "bookings", label: t`Resource staff grants` },
  { key: "events.certificate_designer", parent_module: "events", label: t`Certificate designer` },
  { key: "events.api_read", parent_module: "events", label: t`Signed event integration reads` },
  { key: "events.website", parent_module: "events", label: t`Event websites` },
  { key: "events.embed", parent_module: "events", label: t`Event embeds` },
  { key: "bookings.api_read", parent_module: "bookings", label: t`Signed booking integration reads` },
  { key: "bookings.website", parent_module: "bookings", label: t`Resource websites` },
  { key: "bookings.embed", parent_module: "bookings", label: t`Resource embeds` },
  // L17 (#97, #128 C-9): maintenance, To-Buy and warranty under each parent.
  { key: "machines.maintenance", parent_module: "machines", label: t`Machine maintenance` },
  { key: "machines.tobuy", parent_module: "machines", label: t`Machine To-Buy` },
  { key: "machines.warranty", parent_module: "machines", label: t`Machine warranty` },
  { key: "inventory.tobuy", parent_module: null, label: t`Inventory To-Buy` },
  { key: "inventory.warranty", parent_module: null, label: t`Inventory warranty` },
  // L1 (#21, #71, #73, #77): the public event surface.
  { key: "events.short_links", parent_module: "events", label: t`Event short links` },
  { key: "events.online_delivery", parent_module: "events", label: t`Online and hybrid events` },
  { key: "public_site.closed_notice", parent_module: null, label: t`Closed-for-now banner` },
  { key: "events.broadcast_templates", parent_module: "events", label: t`Broadcast templates and designs` },
  { key: "events.approval_digest", parent_module: "events", label: t`Approval digest` },
  { key: "events.anonymous_feedback", parent_module: "events", label: t`Anonymous feedback forms` },
  { key: "events.submission_integrity", parent_module: "events", label: t`GitHub first-commit flag` },
  { key: "events.mentor_chat_alerts", parent_module: "events", label: t`Mentor help chat alerts` },
  { key: "events.organization_sender", parent_module: "events", label: t`Co-host sender name` },
  { key: "notifications.escalation", parent_module: "notifications", label: t`Escalation re-ping` },
  { key: "notifications.web_push", parent_module: "notifications", label: t`Browser notifications` },
  { key: "notifications.inbox_snooze", parent_module: "notifications", label: t`Inbox snooze and archive` },
  { key: "membership.plan_rules", parent_module: "membership", label: t`Plan types and rules` },
  { key: "membership.public_plans", parent_module: "membership", label: t`Public plan pages` },
  { key: "membership.renewal_desk", parent_module: "membership", label: t`Renewal desk` },
  { key: "membership.import", parent_module: "membership", label: t`Member import` },
  { key: "membership.admission_tools", parent_module: "membership", label: t`Invite links and bulk decisions` },
  { key: "membership.member_numbers", parent_module: "membership", label: t`Member numbers` },
  { key: "membership.records", parent_module: "membership", label: t`Member record fields` },
  { key: "membership.titles", parent_module: "membership", label: t`Member titles` },
  { key: "membership.consent", parent_module: "membership", label: t`Consent ledger` },
  { key: "membership.erasure", parent_module: "membership", label: t`Erasure requests` },
  { key: "membership.history", parent_module: "membership", label: t`Membership history` },
  { key: "membership.register_tools", parent_module: "membership", label: t`Register filters and export` },
  { key: "membership.insights", parent_module: "membership", label: t`Membership insights` },
  { key: "membership.monthly_summary", parent_module: "membership", label: t`Monthly staff summary` },
  { key: "billing.tax", parent_module: null, label: t`Tax on charges` },
  { key: "billing.maker_checker", parent_module: null, label: t`Two-person check for offline income` },
  { key: "billing.offline_claims", parent_module: null, label: t`UPI QR and “I’ve paid” claims` },
  { key: "billing.pay_links", parent_module: null, label: t`Pay links for people without an account` },
  { key: "billing.disputes", parent_module: null, label: t`Payment disputes` },
  { key: "billing.capture_flags", parent_module: null, label: t`Unexpected online payments` },
  { key: "finance.ledger", parent_module: null, label: t`Finance ledger` },
  { key: "charges.pricing", parent_module: null, label: t`Price lists` },
  { key: "charges.discounts", parent_module: null, label: t`Member discounts` },
  { key: "loans.fee_waivers", parent_module: "request_workflow", label: t`Waive loan fees` },
  // L12 (#76, #94, #140-#142): machines and loans depth.
  { key: "inventory.consumables", parent_module: null, label: t`Consumables` },
  { key: "inventory.vendors", parent_module: null, label: t`Vendors` },
  { key: "inventory.expected_back", parent_module: "public_inventory", label: t`Expected-back dates` },
  { key: "loans.reservations", parent_module: "request_workflow", label: t`Loan reservations` },
  { key: "loans.pickup_windows", parent_module: "request_workflow", label: t`Pickup windows` },
  { key: "loans.waitlist", parent_module: "request_workflow", label: t`Loan waitlist` },
  { key: "loans.withdrawals", parent_module: "request_workflow", label: t`Withdraw requests` },
  { key: "machines.job_requests", parent_module: "machine_service", label: t`Machine job requests` },
  { key: "machines.job_quotes", parent_module: "machine_service", label: t`Job quotes` },
  { key: "machines.batch_start", parent_module: "machine_service", label: t`Batch start` },
  { key: "machines.pay_before_pickup", parent_module: "machine_service", label: t`Pay before pickup` },
  { key: "machines.time_booking", parent_module: "machines", label: t`Machine time booking` },
  { key: "mobile.watch_actions", parent_module: "mobile", label: t`Watch-friendly push actions` },
  // L23 (#158): metered machine sessions.
  { key: "machines.sessions", parent_module: "machines", label: t`Machine sessions` },
  // L16 (#128 C-3/C-9): repairs, issue reporting and maintenance under each parent.
  { key: "machines.repairs", parent_module: "machines", label: t`Machine repairs & technicians` },
  { key: "machines.issue_reporting", parent_module: "machines", label: t`Machine issue reporting` },
  { key: "inventory.maintenance", parent_module: null, label: t`Inventory maintenance` },
  { key: "inventory.repairs", parent_module: null, label: t`Inventory repairs & technicians` },
  { key: "inventory.issue_reporting", parent_module: null, label: t`Inventory issue reporting` },
  { key: "bookings.room_maintenance", parent_module: "bookings", label: t`Room maintenance` },
  { key: "bookings.room_repairs", parent_module: "bookings", label: t`Room repairs` },
  { key: "bookings.issue_reporting", parent_module: "bookings", label: t`Room issue reporting` },
  // GAP2 M2: due and overdue reminders for item and room maintenance.
  { key: "inventory.maintenance_reminders", parent_module: null, label: t`Item maintenance reminders` },
  { key: "bookings.room_maintenance_reminders", parent_module: "bookings", label: t`Room maintenance reminders` },
  // L3 (#128, #132, #133): ID cards, programmes, event cards, tickets, wallet passes.
  { key: "membership.id_programmes", parent_module: "membership", label: t`ID programmes` },
  { key: "membership.wallet_passes", parent_module: "membership", label: t`Wallet passes for member cards` },
  { key: "events.id_cards", parent_module: "events", label: t`Event ID cards` },
  { key: "events.ticket_designs", parent_module: "events", label: t`Ticket designs` },
  { key: "events.wallet_passes", parent_module: "events", label: t`Wallet passes for event cards` },
  // L13 (#74, #128 C-12/C-13): a public Google Sheet as an import source.
  { key: "membership.import_sheets", parent_module: "membership", label: t`Member import from Google Sheets` },
  { key: "membership.id_programmes_import_sheets", parent_module: "membership", label: t`ID-programme import from Google Sheets` },
  // L6 (#69, #71, #128 C-20): paid ticketing v2 and venue fees.
  { key: "events.orders", parent_module: "events", label: t`Ticket orders` },
  { key: "events.seat_holds", parent_module: "events", label: t`Checkout seat holds` },
  { key: "events.addons", parent_module: "events", label: t`Ticket add-ons` },
  { key: "events.series_passes", parent_module: "events", label: t`Series passes` },
  { key: "events.transfers", parent_module: "events", label: t`Ticket transfers and type changes` },
  { key: "events.desk_collect", parent_module: "events", label: t`Collect payment at the desk` },
  { key: "events.refund_override", parent_module: "events", label: t`Per-event refund policy` },
  { key: "events.venue_fees", parent_module: "events", label: t`Venue fees for hosting` },
  // L18 (#94, #96, #128 C-14): donations, sponsors and calendar sync.
  { key: "finance.donations", parent_module: null, label: t`Donations` },
  { key: "finance.recurring_donations", parent_module: null, label: t`Recurring donations` },
  { key: "finance.sponsors", parent_module: null, label: t`Sponsors` },
  { key: "finance.tax_exempt_receipts", parent_module: null, label: t`Tax-exempt donation receipts` },
  { key: "charges.donations", parent_module: null, label: t`Track donation and sponsor money` },
  { key: "payments.donations", parent_module: "payments", label: t`Donation payments` },
  { key: "bookings.calendar_feed", parent_module: "bookings", label: t`Booking calendar feed` },
  { key: "events.calendar_feed", parent_module: "events", label: t`Event calendar feed` },
  { key: "events.shifts_feed", parent_module: "events", label: t`Shift calendar feed` },
  { key: "calendar.combined_feed", parent_module: null, label: t`Combined personal calendar` },
  { key: "events.public_feed", parent_module: "events", label: t`Public events calendar` },
  // L21a (#128 C-32..C-36): applications for any event, review stages, attendance, crew, check-in lists.
  { key: "events.applications", parent_module: "events", label: t`Applications for any event` },
  { key: "events.application_stages", parent_module: "events", label: t`Application review stages` },
  { key: "events.attendance_confirmation", parent_module: "events", label: t`Attendance confirmation` },
  { key: "events.crew", parent_module: "events", label: t`Event crew` },
  { key: "events.crew_claims", parent_module: "events", label: t`Crew expense claims` },
  { key: "events.checkin_lists", parent_module: "events", label: t`Custom check-in lists` },
  // L21b (X40, X50-X54, #128 C-37..C-39): finalists, prize payouts, fees, paid teams, saved views, gallery search.
  { key: "events.finalists", parent_module: "events", label: t`Finalists` },
  { key: "events.prize_payouts", parent_module: "events", label: t`Prize money and payouts` },
  { key: "events.entry_fees", parent_module: "events", label: t`Project entry fees` },
  { key: "events.paid_teams", parent_module: "events", label: t`Paid team registration` },
  { key: "events.saved_views", parent_module: "events", label: t`Saved views and exports for event lists` },
  { key: "events.gallery_search", parent_module: "events", label: t`Gallery search and awards` },
  // Hack-money (#180): prize splits and claims, refundable deposits, add-ons for accepted participants.
  { key: "events.prize_claims", parent_module: "events", label: t`Prize splits and winner claims` },
  { key: "events.deposits", parent_module: "events", label: t`Refundable hackathon deposits` },
  { key: "events.accepted_addons", parent_module: "events", label: t`Add-ons for accepted participants` },
  // r2-peoples-choice (#181 S3): an optional People's choice award voted on the public gallery.
  { key: "events.peoples_choice", parent_module: "events", label: t`People's choice award` },
  // L24 (#163A): price-drop refunds.
  { key: "charges.price_drop_refunds", parent_module: null, label: t`Price-drop refunds` },
  // L22 (#128 C-7, #129, #135, #137): the per-space shop.
  { key: "shop.online", parent_module: "shop", label: t`Online shop` },
  { key: "shop.guest_checkout", parent_module: "shop", label: t`Guest checkout` },
  { key: "shop.holds", parent_module: "shop", label: t`Stock holds at checkout` },
  { key: "shop.member_prices", parent_module: "shop", label: t`Member prices` },
  { key: "shop.tax", parent_module: "shop", label: t`Shop tax classes` },
  { key: "shop.returns", parent_module: "shop", label: t`Returns and refunds` },
  { key: "shop.cash_up", parent_module: "shop", label: t`Cash-up` },
  { key: "shop.event_pickup", parent_module: "shop", label: t`Pickup at events` },
  { key: "shop.order_limits", parent_module: "shop", label: t`Per-order limits` },
  { key: "shop.public_stock", parent_module: "shop", label: t`Stock on the shop page` },
  { key: "shop.receipts", parent_module: "shop", label: t`Shop receipts` },
  { key: "shop.reorder", parent_module: "shop", label: t`Low-stock reorder` },
  { key: "shop.bundles", parent_module: "shop", label: t`Kit bundles` },
  { key: "shop.consumable_link", parent_module: "shop", label: t`Sell inventory consumables` },
  { key: "charges.shop", parent_module: "shop", label: t`Track shop sales` },
  { key: "payments.shop", parent_module: "shop", label: t`Online shop payments` },
  // L20 (#69, #128 C-31): the in-app help centre.
  { key: "platform.help_centre", parent_module: null, label: t`Help centre` },
];

export function featureEnabled(features: Iterable<string>, key: string) {
  return new Set(features).has(key);
}

/** Security keys live in the Security panel (Space Manager/superadmin, re-auth, audit), never in Features. */
export function isSecurityFeature(key: string) {
  return key.startsWith("security.");
}

/** The heading a feature is listed under: its parent module, or the parentless families. */
export function featureGroup(feature: FeatureDefinition) {
  if (feature.parent_module) return feature.parent_module;
  return feature.key.startsWith("inventory.") || feature.key.startsWith("loans.") ? "inventory" : "general";
}

/**
 * Effective switch as the console can see it: stored, and its parent module installed.
 * Mirrors `capability_eligibility.configuration_feature_enabled` for one level; the server
 * still decides (a route whose switch is off answers 404).
 */
export function capabilityOn(
  makerspace: { enabled_modules?: string[]; enabled_features?: string[] } | undefined, key: string,
) {
  if (!makerspace?.enabled_features?.includes(key)) return false;
  const parent = FEATURE_DEFINITIONS.find(feature => feature.key === key)?.parent_module;
  return !parent || (makerspace.enabled_modules ?? []).includes(parent);
}
