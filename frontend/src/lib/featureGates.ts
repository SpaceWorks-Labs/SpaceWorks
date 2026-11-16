import type { FeatureDefinition } from "./features";

// Pure switch helpers split out of features.ts (300-line ceiling); features.ts re-exports them.
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

/** Children of the Inventory switch (`loans.enabled`); consumables, vendors and fee waivers keep their own state. */
export const INVENTORY_CHILD_FEATURES: ReadonlySet<string> = new Set([
  "inventory.self_checkout", "inventory.kiosk", "inventory.contact_self_checkout", "inventory.expected_back",
  "inventory.issue_reporting", "inventory.maintenance", "inventory.maintenance_reminders", "inventory.notify_when_back",
  "inventory.repairs", "inventory.tobuy", "inventory.warranty", "loans.renewals", "loans.limits", "loans.kit_checklist",
  "loans.reservations", "loans.pickup_windows", "loans.waitlist", "loans.withdrawals",
]);
