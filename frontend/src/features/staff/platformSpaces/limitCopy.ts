import { t } from "@lingui/core/macro";

/**
 * Plain-language copy for the platform console's limits and request rates (decision 235):
 * each says what is counted and what happens at the limit. Keys come from the server; an
 * unknown key still gets a readable label and a generic line, never raw snake_case.
 */
const humanize = (key: string) => {
  const text = key.replace(/_/g, " ").trim();
  return text.charAt(0).toUpperCase() + text.slice(1);
};

// The server sends an English label (limits_core.RESOURCE_LABELS); a function, so the words
// follow a language switch. The server label is only the fallback for a key added later.
const LIMIT_NAMES = (): Record<string, string> => ({
  products: t`Products`, assets: t`Assets`, machines: t`Machines`, events: t`Events`,
  events_monthly: t`New events this month`, bookings: t`Active bookings`, staff: t`Staff members`, members: t`Members`,
  storage: t`Storage`, upload_bytes: t`Largest single upload`, print: t`Print requests per month`,
  email: t`Emails per day`, email_monthly: t`Emails this month`, sms: t`Text messages per day`,
  sms_monthly: t`Text messages this month`, whatsapp: t`WhatsApp messages per day`, whatsapp_monthly: t`WhatsApp messages this month`,
  telegram: t`Telegram notifications per day`, slack: t`Slack notifications per day`,
  mattermost: t`Mattermost notifications per day`, discord: t`Discord notifications per day`,
  webhook: t`Signed webhook deliveries per day`, native_push: t`App push notifications per day`,
  api_clients: t`API clients`, machine_service_open: t`Open machine service requests`,
  machine_service_submit: t`Machine service requests per day`, data_exports: t`Data exports running`,
  guest_passes: t`Guest and day passes per day`, custom_domain: t`Custom domain`,
  otp_email: t`Sign-in code emails per day`, otp_sms: t`Sign-in code texts per day`,
  // Decisions 281/284: monthly quotas (any space) and the platform's credentials (counted only when used).
  bookings_monthly: t`New bookings this month`, payments_monthly_count: t`Paid transactions this month`,
  payments_monthly_amount: t`Money taken this month`, platform_email_monthly: t`Emails through the platform this month`,
  platform_sms_monthly: t`Texts through the platform this month`, platform_whatsapp_monthly: t`WhatsApp messages through the platform this month`,
  platform_push_monthly: t`App pushes through the platform this month`, platform_wallet_monthly: t`Wallet passes through the platform this month`,
  platform_payments_monthly_count: t`Online payments through the platform this month`,
  platform_payments_monthly_amount: t`Money taken through the platform this month`,
  event_registrations_monthly: t`Event registrations this month`, shop_orders_monthly: t`Shop orders this month`,
  shop_products: t`Shop products`, membership_plans: t`Membership plans`, donation_campaigns: t`Donation campaigns`,
  bookable_spaces: t`Bookable rooms and spaces`, boxes: t`Boxes`, organizations_linked: t`Linked organizations`,
  api_requests_per_minute: t`API requests per minute`, analytics_connections: t`Analytics connections`,
  report_exports_monthly: t`Report exports this month`, kiosk_stations: t`Kiosk stations`, devices: t`Devices`,
  machine_jobs_monthly: t`Machine jobs this month`, machine_sessions_monthly: t`Machine sessions this month`,
  storage_evidence_bytes: t`Storage for evidence photos`, storage_public_images_bytes: t`Storage for public images`,
  webhook_endpoints: t`Outbound webhook endpoints`,
  staff_cards_issued_monthly: t`Staff ID cards issued this month`,
  photo_cutout_jobs_monthly: t`Card photo background removals this month`,
  card_templates: t`Saved card and certificate templates`,
  paired_displays: t`Paired display screens`,
  adapter_bridges: t`Enrolled device adapters`,
  adapter_watch_streams: t`Camera watch sessions open at once`,
  adapter_snapshots: t`Camera snapshots requested this month`,
  adapter_artifacts: t`Adapter timelapses, previews and bundles kept`,
  // 0.12.0 (decision 328a): the module-by-module sweep.
  hardware_requests_monthly: t`Hardware requests this month`, stock_transfers_monthly: t`Stock transfers this month`,
  stocktake_sessions_monthly: t`Stocktake sessions this month`, shelf_checks_monthly: t`Shelf checks this month`, reimbursement_claims_monthly: t`Reimbursement claims this month`,
  public_page_assets: t`Images on the public page`, scheduled_reports: t`Scheduled reports`,
  adapter_media_bytes: t`Storage for adapter media`, adapter_telemetry_points: t`Device telemetry samples kept`,
  anthias_players: t`Anthias display players`,
});

/** A limit or usage resource key as people read it; the server's label, then the key, only for an unknown one. */
export function limitLabel(key: string, label?: string) {
  const text = LIMIT_NAMES()[key] ?? (label && label !== key ? label : humanize(key));
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function limitHint(key: string) {
  switch (key) {
    case "members": return t`People with a membership here. At the limit, new joins wait until a place frees up.`;
    case "staff": return t`People with a staff role. At the limit, no more staff can be added or invited.`;
    case "storage": return t`Space used by photos, files and evidence. At the limit, new uploads are refused.`;
    case "upload_bytes": return t`Largest single file a person can upload. Bigger files are refused.`;
    case "products": return t`Items in the inventory. At the limit, no new items can be added.`;
    case "assets": return t`Individually tracked tools (with their own QR code). At the limit, no new ones can be added.`;
    case "machines": return t`Machines registered for booking or jobs. At the limit, no new machines can be added.`;
    case "events": return t`Events this space has in total. At the limit, no new events can be created.`;
    case "events_monthly": return t`New events created this month. At the limit, new events wait for next month.`;
    case "bookings": return t`Upcoming bookings at once. At the limit, new bookings are refused until one ends.`;
    case "api_clients": return t`Apps and integrations connected to this space. At the limit, no new ones can be added.`;
    case "webhook_endpoints": return t`Addresses this space sends signed webhooks to. At the limit, no new endpoints can be added.`;
    case "staff_cards_issued_monthly": return t`Staff ID cards issued per month. At the limit, more wait until next month.`;
    case "photo_cutout_jobs_monthly": return t`Card photo background removals per month. At the limit, new ones wait until next month; existing cut-outs keep working.`;
    case "card_templates": return t`Saved card and certificate templates. At the limit, no more can be saved, duplicated or imported; the built-in looks stay available.`;
    case "guest_passes": return t`Guest and day passes issued per day. At the limit, more passes wait until tomorrow.`;
    case "data_exports": return t`Data exports running at once. At the limit, a new export waits for one to finish.`;
    case "print": return t`Print requests per month. At the limit, new requests wait for next month.`;
    case "machine_service_open": return t`Open machine service requests. At the limit, new requests wait until one closes.`;
    case "machine_service_submit": return t`Machine service requests per day. At the limit, more wait until tomorrow.`;
    case "custom_domain": return t`Whether this space may use its own domain name.`;
    case "email": case "email_monthly": return t`Emails sent by this space. At the limit, further emails wait until the count resets.`;
    case "sms": case "sms_monthly": return t`Text messages sent by this space. At the limit, further texts are not sent.`;
    case "whatsapp": case "whatsapp_monthly": return t`WhatsApp messages sent by this space. At the limit, further messages are not sent.`;
    case "telegram": case "slack": case "mattermost": case "discord": case "native_push": case "webhook":
      return t`Notifications sent through this channel per day. At the limit, more wait until tomorrow.`;
    case "bookings_monthly": return t`Bookings created this month, cancelled ones included. At the limit, new bookings wait for next month.`;
    case "payments_monthly_count": case "payments_monthly_amount":
      return t`New paid transactions this month on any rail (amounts per currency, in whole units). At the limit, new charges are refused; existing charges can always be paid.`;
    case "platform_email_monthly": case "platform_sms_monthly": case "platform_whatsapp_monthly": case "platform_push_monthly":
      return t`Counted only when the platform's credentials send for this space; its own credentials are never limited. At the limit, that channel skips and the inbox still delivers.`;
    case "platform_wallet_monthly": return t`New wallet passes signed with the platform's certificates. At the limit, new passes wait for next month.`;
    case "platform_payments_monthly_count": case "platform_payments_monthly_amount":
      return t`Online payments through the platform's payment account (amounts per currency, in whole units). At the limit, pay at the desk or the space's own account still works.`;
    case "api_requests_per_minute": return t`Requests from this space's API clients each minute. Above it, clients are told to slow down.`;
    case "storage_evidence_bytes": case "storage_public_images_bytes": return t`Space used by these files. At the limit, new uploads of this kind are refused.`;
    case "event_registrations_monthly": case "shop_orders_monthly": case "report_exports_monthly": case "machine_jobs_monthly": case "machine_sessions_monthly":
      return t`Counted this month. At the limit, new ones wait for next month.`;
    case "hardware_requests_monthly": case "stock_transfers_monthly": case "stocktake_sessions_monthly": case "shelf_checks_monthly": case "reimbursement_claims_monthly":
      return t`Counted this month. At the limit, new ones wait for next month; existing ones carry on.`;
    case "public_page_assets": return t`Images uploaded for the public space page. At the limit, no more can be uploaded; published pages are unchanged.`;
    case "scheduled_reports": return t`Reports that are scheduled to send. At the limit, no new schedule can be created.`;
    case "adapter_media_bytes": return t`Space used by timelapses, previews and bundles from device adapters. At the limit, new uploads are refused; old ones expire as usual.`;
    case "adapter_telemetry_points": return t`Device readings kept for history charts. At the limit, new readings are not stored; stored ones stay until they expire.`;
    case "anthias_players": return t`Anthias display players registered for the space screens. At the limit, no new player can be added.`;
    default: return t`At the limit, new ones are refused until usage drops or the limit is raised.`;
  }
}

export function limitSource(source: "own" | "override" | "plan" | "default" | "unlimited") {
  switch (source) {
    case "own": return t`own space`;
    case "override": return t`set for this space`;
    case "plan": return t`from the plan`;
    case "default": return t`platform default`;
    case "unlimited": return t`no limit`;
  }
}

const RATES: Record<string, () => [string, string]> = {
  card_verify: () => [t`Checking a member card`, t`Public card checks per person. Past the rate, checks are paused briefly.`],
  card_render: () => [t`Printing card sheets`, t`Staff card sheet previews.`],
  member_card_resolve: () => [t`Looking up people and cards`, t`Staff searches and card scans at the desk.`],
  minor_person_lookup: () => [t`Looking up young members`, t`Guardian and minor searches by staff.`],
  id_join: () => [t`Joining with an ID card`, t`Join attempts with a programme ID per person.`],
  id_join_upload: () => [t`ID card photo uploads`, t`Photos sent with an ID join request.`],
  pay_links: () => [t`Opening payment links`, t`Pay-link requests per person.`],
  payment_claims: () => [t`"I've paid" claims`, t`Claims that a payment was made offline.`],
  pricing_quote: () => [t`Price previews`, t`Price checks before booking or buying.`],
  peoples_choice_vote: () => [t`People's choice votes`, t`Votes per person at an event.`],
  shop_orders: () => [t`Shop orders`, t`New shop orders per person.`],
  shop_codes: () => [t`Shop discount codes`, t`Discount code attempts per person.`],
  event_orders: () => [t`Event ticket orders`, t`New ticket orders per person.`],
  login: () => [t`Sign-in attempts`, t`Password sign-in attempts per person and address.`],
  anon: () => [t`Visitors not signed in`, t`All requests from one address while signed out.`],
  user: () => [t`Signed-in people`, t`All requests from one signed-in account.`],
};

export function rateLabel(scope: string) {
  return RATES[scope]?.()[0] ?? humanize(scope);
}

/** What the rate limits; every rate shares the same at-the-limit behaviour. */
export function rateHint(scope: string) {
  const what = RATES[scope]?.()[1] ?? t`Requests of this kind per person or address.`;
  return t`${what} Above the rate, people see "Too many requests" and can try again shortly.`;
}
