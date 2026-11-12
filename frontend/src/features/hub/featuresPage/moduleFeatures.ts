import { RETIRED_FEATURES } from "../../../lib/retiredFeatures";
import { FEATURE_DEFINITIONS, isSecurityFeature, type FeatureDefinition } from "../../../lib/features";
import type { ModuleKey } from "../../../lib/retiredModules";
import { MODULE_GROUP } from "./moduleGroups";

/**
 * Which module page lists a feature switch. A switch with a parent module belongs to it. The 40 parentless
 * switches are placed by key (an exact key first, then its family prefix), defaulting to the staff console.
 * Every listed switch appears on exactly one page (the guard in moduleFeatures.test.ts); security switches
 * live in their own settings panel and retired ones are always off, so neither is a product feature.
 */
const KEY_HOME: Record<string, ModuleKey> = {
  "inventory.self_checkout": "public_inventory", "inventory.contact_self_checkout": "public_inventory",
  "inventory.kiosk": "public_inventory", "public_site.closed_notice": "public_inventory",
  "presence.geofence": "presence", "calendar.combined_feed": "bookings", "legal.space_pages": "member_accounts",
};
const FAMILY_HOME: Record<string, ModuleKey> = { billing: "payments", charges: "payments", finance: "payments" };

export function moduleOfFeature(feature: FeatureDefinition): ModuleKey {
  if (feature.parent_module && feature.parent_module in MODULE_GROUP) return feature.parent_module as ModuleKey;
  return KEY_HOME[feature.key] ?? FAMILY_HOME[feature.key.split(".")[0]] ?? "staff_admin";
}

export const isProductFeature = (feature: FeatureDefinition) => !RETIRED_FEATURES.has(feature.key) && !isSecurityFeature(feature.key);

export function featuresByModule(): Record<ModuleKey, FeatureDefinition[]> {
  const out = Object.fromEntries((Object.keys(MODULE_GROUP) as ModuleKey[]).map(key => [key, [] as FeatureDefinition[]])) as Record<ModuleKey, FeatureDefinition[]>;
  for (const feature of FEATURE_DEFINITIONS.filter(isProductFeature)) out[moduleOfFeature(feature)].push(feature);
  return out;
}

/** A module's switches grouped by key family (`machines.`, `maintenance.` ...), in registry order. */
export function featureFamilies(features: FeatureDefinition[]): { family: string; features: FeatureDefinition[] }[] {
  const families = new Map<string, FeatureDefinition[]>();
  for (const feature of features) {
    const family = feature.key.split(".")[0];
    families.set(family, [...(families.get(family) ?? []), feature]);
  }
  return [...families].map(([family, list]) => ({ family, features: list }));
}
