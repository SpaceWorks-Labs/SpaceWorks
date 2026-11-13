import { t } from "@lingui/core/macro";
import { RETIRED_MODULE_ALIASES, type ModuleKey } from "../../../lib/retiredModules";

/**
 * The groups of the module switch screens, in the same order and with the same members as the backend
 * registry (apps/makerspaces/module_registry_definitions.py GROUPS and each module's `group=`).
 * moduleGroups.test.ts parses those Python files and fails when this mirror drifts. Typed by the live module
 * keys (generated ModulesEnum minus retired keys), so a newly registered module is a type error here until it
 * is placed. A retired key (`printing`, decision 340b) has no group and no page of its own.
 */
export type ModuleGroupKey = "inventory" | "stocktake" | "machines" | "events" | "bookings" | "membership" | "notifications"
  | "reports" | "payments" | "mobile" | "devices" | "shop";

export const GROUP_ORDER: readonly ModuleGroupKey[] = ["inventory", "stocktake", "machines", "events", "bookings", "membership",
  "notifications", "reports", "payments", "mobile", "devices", "shop"];

export const MODULE_GROUP: Record<ModuleKey, ModuleGroupKey> = {
  public_inventory: "inventory", request_workflow: "inventory", staff_admin: "inventory", guest_handover: "inventory",
  scanner: "inventory", evidence_uploads: "inventory", qr_management: "inventory", bulk_import: "inventory",
  containers: "inventory", stock_transfers: "inventory", qr_print_batches: "inventory", asset_units: "inventory",
  stocktake: "stocktake", machines: "machines", machine_service: "machines",
  events: "events", event_reimbursements: "events", bookings: "bookings",
  membership: "membership", member_accounts: "membership", presence: "membership",
  notifications: "notifications", email: "notifications", telegram: "notifications", slack: "notifications",
  mattermost: "notifications", discord: "notifications", sms: "notifications", whatsapp: "notifications", webhook: "notifications",
  reports: "reports", analytics: "reports", payments: "payments", mobile: "mobile", devices: "devices", shop: "shop",
};

export type ModuleGroup = { key: ModuleGroupKey; title: string; summary: string; modules: ModuleKey[] };

const GROUP_TEXT = (): Record<ModuleGroupKey, [string, string]> => ({
  inventory: [t`Inventory`, t`The catalogue, loans, QR and photo evidence, and everything that moves stock. On by default; a space can switch it off.`],
  stocktake: [t`Stocktake`, t`Scan-first stock counts and variance reports.`],
  machines: [t`Machines`, t`Machine registry, job queues, access and maintenance.`],
  events: [t`Events`, t`Tickets, check-in, badges, certificates and reimbursements.`],
  bookings: [t`Bookings`, t`Rooms, benches and equipment booked with rules and passes.`],
  membership: [t`Membership`, t`Plans, member accounts, ID cards, profiles and presence.`],
  notifications: [t`Notifications and chat`, t`The in-app inbox and every outbound channel.`],
  reports: [t`Reports and analytics`, t`The report catalogue, exports and dashboards.`],
  payments: [t`Payments`, t`Money owed, receipts and optional online checkout.`],
  mobile: [t`Mobile apps`, t`Attested device sessions, native push and the payment sheet.`],
  devices: [t`Connected devices`, t`Printers, media players and adapters with their own keys.`],
  shop: [t`Shop`, t`Consumables, kits and merchandise at the desk and online.`],
});

export function moduleGroups(): ModuleGroup[] {
  const text = GROUP_TEXT();
  return GROUP_ORDER.map(key => ({
    key, title: text[key][0], summary: text[key][1],
    modules: (Object.keys(MODULE_GROUP) as ModuleKey[]).filter(module => MODULE_GROUP[module] === key),
  }));
}

/** URL form of a module key: `guest_handover` is `/features/guest-handover`. */
export const moduleSlug = (key: string) => key.replace(/_/g, "-");
export const moduleFromSlug = (slug: string | undefined): ModuleKey | null => {
  const key = (slug ?? "").replace(/-/g, "_");
  return Object.prototype.hasOwnProperty.call(MODULE_GROUP, key) ? (key as ModuleKey) : null;
};
/** Where an old link to a retired module's page goes: `/features/printing` is `/features/machine-service`. */
export const retiredModuleRedirect = (slug: string | undefined): string | null => {
  const key = (slug ?? "").replace(/-/g, "_");
  const live = (RETIRED_MODULE_ALIASES as Record<string, string>)[key];
  return live ? `/features/${moduleSlug(live)}` : null;
};
