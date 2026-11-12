import { t } from "@lingui/core/macro";
import type { ModuleKey } from "../../../lib/retiredModules";
import { RETIRED_FEATURES } from "../../../lib/retiredFeatures";
import { FEATURE_DEFINITIONS, featureGroup, isSecurityFeature, type FeatureDefinition } from "../../../lib/features";

/**
 * The public feature list (/features, decision 306 b). The module keys and every feature switch come from
 * the app's own catalogue (generated ModulesEnum minus retired keys, lib/features.ts, lib/featureHelp.ts), so nothing here
 * is a hand-copied list. What is curated is small: each area's summary, three "what you get" lines,
 * its docs page, and each module's default. Areas follow setup (apps/makerspaces/setup_areas.py),
 * with the always-on services, organizations and the platform added. Typed by ModuleKey, so a newly
 * registered module is a type error here until it is placed.
 */
export type ModuleDefault = "always" | "on" | "off";
export type FeatureArea = {
  key: string; title: string; summary: string; gets: string[]; docs: string; modules: ModuleKey[];
  /** For areas that are not modules: how they are switched on. */
  availability?: string;
};

/** Core and always-installed modules, then setup's default-yes areas (Inventory, Machines, Reports). */
const MODULE_DEFAULTS: Record<ModuleKey, ModuleDefault> = {
  public_inventory: "always", request_workflow: "always", staff_admin: "always", scanner: "always",
  evidence_uploads: "always", qr_management: "always", notifications: "always", email: "always", member_accounts: "always",
  guest_handover: "on", asset_units: "on", containers: "on", bulk_import: "on", stock_transfers: "on",
  qr_print_batches: "on", stocktake: "on", devices: "on", machines: "on", machine_service: "on", reports: "on",
  events: "off", event_reimbursements: "off", bookings: "off", membership: "off", presence: "off", mobile: "off",
  payments: "off", shop: "off", analytics: "off", sms: "off", whatsapp: "off", telegram: "off", slack: "off",
  mattermost: "off", discord: "off", webhook: "off",
};

export const moduleDefault = (key: ModuleKey) => MODULE_DEFAULTS[key];

export function featureAreas(): FeatureArea[] {
  return [
    { key: "inventory", title: t`Inventory`, docs: "/docs/modules/inventory",
      summary: t`A public catalogue, borrow requests that staff review, and a handover record for every loan.`,
      gets: [t`Box QR scan and photo before anything leaves; return photo and remark before it comes back`,
        t`Kits, containers, stocktakes, consumables and a To-Buy list`, t`Self-checkout and a kiosk station when a space allows it`],
      modules: ["public_inventory", "request_workflow", "staff_admin", "scanner", "evidence_uploads", "qr_management",
        "guest_handover", "asset_units", "containers", "bulk_import", "stock_transfers", "qr_print_batches", "stocktake", "devices"] },
    { key: "machines", title: t`Machines`, docs: "/docs/modules/machines",
      summary: t`Job queues for printers, lasers and CNC, machine access given by a space manager, and maintenance.`,
      gets: [t`Job requests, quotes and pickup`, t`Machine access given by a space manager`, t`Maintenance by date or hours of use`],
      modules: ["machines", "machine_service"] },
    { key: "events", title: t`Events`, docs: "/docs/modules/events",
      summary: t`From sign-up to certificate: tickets, check-in, badges and hackathon programmes.`,
      gets: [t`Free or paid tickets, ticket types and promo codes`, t`Badge designer with role variants and desk printing`,
        t`Offline check-in, certificates and a project gallery`],
      modules: ["events", "event_reimbursements"] },
    { key: "bookings", title: t`Bookings`, docs: "/docs/modules/bookings",
      summary: t`Rooms, benches and equipment booked properly, with rules, passes and calendars.`,
      gets: [t`One-off and recurring bookings`, t`Printable passes and check-in`, t`Calendar feeds and an embeddable page`],
      modules: ["bookings"] },
    { key: "membership", title: t`Membership, accounts and ID cards`, docs: "/docs/modules/memberships",
      summary: t`Plans and renewals, the member area, and custom ID cards with a public check page.`,
      gets: [t`Card designer for member cards and staff ID cards, with numbering`, t`Desk printing at card size, bulk sheets and PDF`,
        t`Wallet passes and a QR that anyone can check`],
      modules: ["membership", "member_accounts", "presence", "mobile"] },
    { key: "payments", title: t`Payments and money`, docs: "/docs/modules/payments",
      summary: t`Money owed is tracked without any provider; online checkout through Stripe or Razorpay is optional.`,
      gets: [t`Charges, receipts and offline settlement`, t`Online checkout for bookings, events, machines and plans`, t`Reminders for money due`],
      modules: ["payments"] },
    { key: "shop", title: t`Shop`, docs: "/docs/modules/shop",
      summary: t`Sell consumables and merchandise from the same space, without a second system.`,
      gets: [t`Consumables, kits and merch with sizes and stock`, t`A public shop page for pickup, and a front-desk till`, t`Every sale in the same ledger and reports`], modules: ["shop"] },
    { key: "reports", title: t`Reports and analytics`, docs: "/docs/modules/analytics",
      summary: t`The report catalogue and exports, with optional Metabase and Grafana dashboards per space.`,
      gets: [t`Saved report views and exports`, t`Post-event PDFs`, t`Dashboards that only ever see their own space`],
      modules: ["reports", "analytics"] },
    { key: "messaging", title: t`Notifications and chat`, docs: "/docs/modules/notifications-and-messaging",
      summary: t`Email and in-app notices for members and staff, and alerts to the team's own chat.`,
      gets: [t`Quiet hours, digests and member preferences`, t`SMS and WhatsApp when connected`,
        t`Telegram, Slack, Mattermost, Discord and signed webhooks, idle until set up`],
      modules: ["notifications", "email", "sms", "whatsapp", "telegram", "slack", "mattermost", "discord", "webhook"] },
    { key: "organizations", title: t`Organizations`, docs: "/docs/modules/organizations",
      summary: t`Accounts for clubs, colleges and companies, their admins, and organization bookings.`,
      gets: [t`Organization admins and members`, t`Links between organizations and spaces`, t`A public directory when turned on`], modules: [],
      availability: t`Part of every install; the public directory is off until the server owner turns it on` },
    { key: "platform", title: t`Platform and hosting`, docs: "/docs/modules/platform",
      summary: t`One server for many spaces: the superadmin console, own or hosted spaces, backups and API clients.`,
      gets: [t`Space lifecycle controls and plans, with no limits by default`, t`Backups and moving a space between servers`,
        t`Scoped API clients for your own tools`], modules: [],
      availability: t`Always there for the server owner; hosting other spaces is off by default` },
  ];
}

/** Which area lists a feature switch: its parent module's area, else by key family. */
export function areaOfFeature(feature: FeatureDefinition, areas: FeatureArea[] = featureAreas()): string {
  const group = featureGroup(feature);
  const owner = areas.find(area => (area.modules as string[]).includes(group));
  if (owner) return owner.key;
  if (group === "inventory") return "inventory";
  const family = feature.key.split(".")[0];
  if (["charges", "billing", "finance", "payments"].includes(family)) return "payments";
  if (["membership", "presence", "cards", "id"].includes(family)) return "membership";
  if (family === "organizations") return "organizations";
  if (family === "events") return "events";
  return "platform";
}

/** Every listed switch (security switches live in their own panel and are not product features). */
export function featuresByArea(areas: FeatureArea[] = featureAreas()): Record<string, FeatureDefinition[]> {
  const out: Record<string, FeatureDefinition[]> = Object.fromEntries(areas.map(area => [area.key, []]));
  for (const feature of FEATURE_DEFINITIONS.filter(row => !RETIRED_FEATURES.has(row.key))) {
    if (isSecurityFeature(feature.key)) continue;
    out[areaOfFeature(feature, areas)].push(feature);
  }
  return out;
}
