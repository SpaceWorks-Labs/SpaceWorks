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
  { key: "notifications.quiet_hours", parent_module: "notifications", label: "Quiet hours" },
  { key: "notifications.digests", parent_module: "notifications", label: "Daily notification digests" },
  { key: "membership.broadcasts", parent_module: "membership", label: "Member broadcasts" },
  { key: "bookings.recurring", parent_module: "bookings", label: "Recurring bookings" },
  { key: "loans.enabled", parent_module: "staff_admin", label: "Hardware loans" },
  { key: "inventory.notify_when_back", parent_module: "public_inventory", label: "Notify when back" },
  { key: "stocktake.discipline", parent_module: "stocktake", label: "Stocktake discipline" },
  { key: "machines.public_detail", parent_module: "machines", label: "Public machine details" },
  { key: "machines.material_catalogue", parent_module: "machines", label: "Local material catalogue" },
  { key: "machines.structured_intake", parent_module: "machine_service", label: "Structured machine intake" },
  { key: "maintenance.meters", parent_module: "machines", label: "Usage-based maintenance" },
  { key: "maintenance.calendar_feed", parent_module: "machines", label: "Maintenance calendar feed" },
  { key: "packs.import", parent_module: "staff_admin", label: "Space packs" },
  { key: "membership.auto_renew", parent_module: "membership", label: "Automatic membership renewal" },
  { key: "membership.lifecycle_mail", parent_module: "membership", label: "Membership lifecycle mail" },
  { key: "membership.self_service", parent_module: "membership", label: "Member account self-service" },
  { key: "membership.self_export", parent_module: "membership", label: "Member data export" },
  { key: "reports.saved_views", parent_module: "reports", label: "Saved report views" },
  { key: "billing.documents", parent_module: null, label: "Receipt documents" },
  { key: "billing.reminders", parent_module: "notifications", label: "Payment reminders" },
  { key: "loans.renewals", parent_module: "request_workflow", label: "Loan renewals" },
  { key: "loans.limits", parent_module: "request_workflow", label: "Borrow limits" },
  { key: "loans.kit_checklist", parent_module: "containers", label: "Kit checklists" },
  { key: "staff.invitations", parent_module: null, label: "Staff invitations" },
  { key: "ui.delight", parent_module: null, label: "Interface effects" },
  { key: "ui.easter_eggs", parent_module: null, label: "Easter eggs" },
  { key: "security.staff_mfa_required", parent_module: null, label: "Require MFA for staff" },
  { key: "membership.vouching", parent_module: "membership", label: "Membership vouching" },
  { key: "membership.application_form", parent_module: "membership", label: "Membership application form" },
  { key: "payments.machines", parent_module: "machines", label: "Machine payments" },
  { key: "payments.bookings", parent_module: "bookings", label: "Booking payments" },
  { key: "payments.events", parent_module: "events", label: "Event payments" },
  { key: "payments.membership", parent_module: "membership", label: "Membership payments" },
  { key: "payments.loans", parent_module: "payments", label: "Loan deposits and late fees" },
  { key: "charges.enabled", parent_module: null, label: "Track money owed" },
  { key: "charges.bookings", parent_module: "bookings", label: "Track booking charges" },
  { key: "charges.events", parent_module: "events", label: "Track event charges" },
  { key: "charges.machines", parent_module: "machines", label: "Track machine job charges" },
  { key: "charges.membership", parent_module: "membership", label: "Track membership charges" },
  { key: "charges.loans", parent_module: "request_workflow", label: "Track loan charges" },
  { key: "inventory.self_checkout", parent_module: null, label: "Self checkout" },
  { key: "inventory.contact_self_checkout", parent_module: null, label: "Self checkout without an account" },
  { key: "payments.enabled", parent_module: "payments", label: "Payments" },
  { key: "mobile.push", parent_module: "mobile", label: "Native push" },
  { key: "presence.geofence", parent_module: null, label: "Presence geofence" },
  { key: "notifications.delegated_recipients", parent_module: "machines", label: "Delegated maintenance recipients" },
  { key: "notifications.member_inbox", parent_module: "notifications", label: "Member inbox" },
  { key: "notifications.member_preferences", parent_module: "notifications", label: "Member communication preferences" },
  { key: "events.invites", parent_module: "events", label: "Event invitations" },
  { key: "events.account_registration", parent_module: "events", label: "Account event registration" },
  { key: "events.organization_audience", parent_module: "events", label: "Participating organizations audience" },
  { key: "bookings.broadcasts", parent_module: "bookings", label: "Booker broadcasts" },
  { key: "events.broadcasts", parent_module: "events", label: "Event broadcasts" },
  { key: "reports.event_pdf", parent_module: "reports", label: "Post-event PDF" },
  { key: "reports.event_exports", parent_module: "reports", label: "Event detail exports" },
  { key: "events.ticket_types", parent_module: "events", label: "Event ticket types" },
  { key: "events.promo_codes", parent_module: "events", label: "Event promo codes" },
  { key: "events.offline_checkin", parent_module: "events", label: "Offline & station check-in" },
  { key: "events.hackathons", parent_module: "events", label: "Hackathon programmes" },
  { key: "events.mentoring", parent_module: "events", label: "Mentor desk" },
  { key: "events.mentor_rounds", parent_module: "events", label: "Mentor check-in rounds" },
  { key: "events.volunteering", parent_module: "events", label: "Volunteer contributions" },
  { key: "events.project_gallery", parent_module: "events", label: "Project gallery" },
  { key: "events.pairwise_judging", parent_module: "events", label: "Pairwise judging" },
  { key: "machines.certification_reminders", parent_module: "machines", label: "Certification reminders" },
  { key: "maintenance.reminders", parent_module: "machines", label: "Maintenance reminders" },
  { key: "machines.certifications", parent_module: "machines", label: "Certification gating" },
  { key: "inventory.kiosk", parent_module: null, label: "Kiosk" },
  { key: "bookings.passes", parent_module: "bookings", label: "Printable booking passes" },
  { key: "bookings.clone", parent_module: "bookings", label: "Clone resources" },
  { key: "bookings.staff_tools", parent_module: "bookings", label: "Staff reservation tools" },
  { key: "bookings.analytics", parent_module: "bookings", label: "Resource analytics" },
  { key: "bookings.utilization_pdf", parent_module: "bookings", label: "Resource utilization PDF" },
  { key: "bookings.exports", parent_module: "bookings", label: "Resource reservation exports" },
  { key: "bookings.confirmations", parent_module: "bookings", label: "Private booking confirmations" },
  { key: "bookings.checkin", parent_module: "bookings", label: "Booking QR arrival" },
  { key: "bookings.staff_grants", parent_module: "bookings", label: "Resource staff grants" },
  { key: "events.certificate_designer", parent_module: "events", label: "Certificate designer" },
  { key: "events.api_read", parent_module: "events", label: "Signed event integration reads" },
  { key: "events.website", parent_module: "events", label: "Event websites" },
  { key: "events.embed", parent_module: "events", label: "Event embeds" },
  { key: "bookings.api_read", parent_module: "bookings", label: "Signed booking integration reads" },
  { key: "bookings.website", parent_module: "bookings", label: "Resource websites" },
  { key: "bookings.embed", parent_module: "bookings", label: "Resource embeds" },
  // L17 (#97, #128 C-9): maintenance, To-Buy and warranty under each parent.
  { key: "machines.maintenance", parent_module: "machines", label: "Machine maintenance" },
  { key: "machines.tobuy", parent_module: "machines", label: "Machine To-Buy" },
  { key: "machines.warranty", parent_module: "machines", label: "Machine warranty" },
  { key: "inventory.tobuy", parent_module: null, label: "Inventory To-Buy" },
  { key: "inventory.warranty", parent_module: null, label: "Inventory warranty" },
  // L1 (#21, #71, #73, #77): the public event surface.
  { key: "events.short_links", parent_module: "events", label: "Event short links" },
  { key: "events.online_delivery", parent_module: "events", label: "Online and hybrid events" },
  { key: "public_site.closed_notice", parent_module: null, label: "Closed-for-now banner" },
  { key: "events.broadcast_templates", parent_module: "events", label: "Broadcast templates and designs" },
  { key: "events.approval_digest", parent_module: "events", label: "Approval digest" },
  { key: "events.anonymous_feedback", parent_module: "events", label: "Anonymous feedback forms" },
  { key: "events.submission_integrity", parent_module: "events", label: "GitHub first-commit flag" },
  { key: "events.mentor_chat_alerts", parent_module: "events", label: "Mentor help chat alerts" },
  { key: "events.organization_sender", parent_module: "events", label: "Co-host sender name" },
  { key: "notifications.escalation", parent_module: "notifications", label: "Escalation re-ping" },
  { key: "notifications.web_push", parent_module: "notifications", label: "Browser notifications" },
  { key: "notifications.inbox_snooze", parent_module: "notifications", label: "Inbox snooze and archive" },
  { key: "membership.plan_rules", parent_module: "membership", label: "Plan types and rules" },
  { key: "membership.public_plans", parent_module: "membership", label: "Public plan pages" },
  { key: "membership.renewal_desk", parent_module: "membership", label: "Renewal desk" },
  { key: "membership.import", parent_module: "membership", label: "Member import" },
  { key: "membership.admission_tools", parent_module: "membership", label: "Invite links and bulk decisions" },
  { key: "membership.member_numbers", parent_module: "membership", label: "Member numbers" },
  { key: "membership.records", parent_module: "membership", label: "Member record fields" },
  { key: "membership.titles", parent_module: "membership", label: "Member titles" },
  { key: "membership.consent", parent_module: "membership", label: "Consent ledger" },
  { key: "membership.erasure", parent_module: "membership", label: "Erasure requests" },
  { key: "membership.history", parent_module: "membership", label: "Membership history" },
  { key: "membership.register_tools", parent_module: "membership", label: "Register filters and export" },
  { key: "membership.insights", parent_module: "membership", label: "Membership insights" },
  { key: "membership.monthly_summary", parent_module: "membership", label: "Monthly staff summary" },
  { key: "billing.tax", parent_module: null, label: "Tax on charges" },
  { key: "billing.maker_checker", parent_module: null, label: "Two-person check for offline income" },
  { key: "billing.offline_claims", parent_module: null, label: "UPI QR and “I’ve paid” claims" },
  { key: "billing.pay_links", parent_module: null, label: "Pay links for people without an account" },
  { key: "billing.disputes", parent_module: null, label: "Payment disputes" },
  { key: "billing.capture_flags", parent_module: null, label: "Unexpected online payments" },
  { key: "finance.ledger", parent_module: null, label: "Finance ledger" },
  { key: "charges.pricing", parent_module: null, label: "Price lists" },
  { key: "charges.discounts", parent_module: null, label: "Member discounts" },
  { key: "loans.fee_waivers", parent_module: "request_workflow", label: "Waive loan fees" },
  // L12 (#76, #94, #140-#142): machines and loans depth.
  { key: "inventory.consumables", parent_module: null, label: "Consumables" },
  { key: "inventory.vendors", parent_module: null, label: "Vendors" },
  { key: "inventory.expected_back", parent_module: "public_inventory", label: "Expected-back dates" },
  { key: "loans.reservations", parent_module: "request_workflow", label: "Loan reservations" },
  { key: "loans.pickup_windows", parent_module: "request_workflow", label: "Pickup windows" },
  { key: "loans.waitlist", parent_module: "request_workflow", label: "Loan waitlist" },
  { key: "loans.withdrawals", parent_module: "request_workflow", label: "Withdraw requests" },
  { key: "machines.job_requests", parent_module: "machine_service", label: "Machine job requests" },
  { key: "machines.job_quotes", parent_module: "machine_service", label: "Job quotes" },
  { key: "machines.batch_start", parent_module: "machine_service", label: "Batch start" },
  { key: "machines.pay_before_pickup", parent_module: "machine_service", label: "Pay before pickup" },
  { key: "machines.time_booking", parent_module: "machines", label: "Machine time booking" },
  // L3 (#128, #132, #133): ID cards, programmes, event cards, tickets, wallet passes.
  { key: "membership.id_programmes", parent_module: "membership", label: "ID programmes" },
  { key: "membership.wallet_passes", parent_module: "membership", label: "Wallet passes for member cards" },
  { key: "events.id_cards", parent_module: "events", label: "Event ID cards" },
  { key: "events.ticket_designs", parent_module: "events", label: "Ticket designs" },
  { key: "events.wallet_passes", parent_module: "events", label: "Wallet passes for event cards" },
  // L6 (#69, #71, #128 C-20): paid ticketing v2 and venue fees.
  { key: "events.orders", parent_module: "events", label: "Ticket orders" },
  { key: "events.seat_holds", parent_module: "events", label: "Checkout seat holds" },
  { key: "events.addons", parent_module: "events", label: "Ticket add-ons" },
  { key: "events.series_passes", parent_module: "events", label: "Series passes" },
  { key: "events.transfers", parent_module: "events", label: "Ticket transfers and type changes" },
  { key: "events.desk_collect", parent_module: "events", label: "Collect payment at the desk" },
  { key: "events.refund_override", parent_module: "events", label: "Per-event refund policy" },
  { key: "events.venue_fees", parent_module: "events", label: "Venue fees for hosting" },
  // L21a (#128 C-32..C-36): applications for any event, review stages, attendance, crew, check-in lists.
  { key: "events.applications", parent_module: "events", label: "Applications for any event" },
  { key: "events.application_stages", parent_module: "events", label: "Application review stages" },
  { key: "events.attendance_confirmation", parent_module: "events", label: "Attendance confirmation" },
  { key: "events.crew", parent_module: "events", label: "Event crew" },
  { key: "events.crew_claims", parent_module: "events", label: "Crew expense claims" },
  { key: "events.checkin_lists", parent_module: "events", label: "Custom check-in lists" },
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
