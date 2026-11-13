import { INVENTORY_CHILD_FEATURES } from "./featureGates";
import { RETIRED_FEATURES } from "./retiredFeatures";
import { FEATURE_DEFINITIONS_1 } from "./featureDefinitions/part1";
import { FEATURE_DEFINITIONS_2 } from "./featureDefinitions/part2";
import { FEATURE_DEFINITIONS_3 } from "./featureDefinitions/part3";
import { FEATURE_DEFINITIONS_4 } from "./featureDefinitions/part4";
import { FEATURE_DEFINITIONS_5 } from "./featureDefinitions/part5";
import type { FeatureDefinition } from "./featureDefinitions/types";
export type { FeatureDefinition };
export { featureEnabled, featureGroup, INVENTORY_CHILD_FEATURES, isSecurityFeature } from "./featureGates";

// Mirrors `capabilities.FEATURE_DEFINITIONS`; the literals live in `featureDefinitions/part*.ts` (backend drift guards parse that folder), concatenated here in registry order.
export const FEATURE_DEFINITIONS: readonly FeatureDefinition[] = [
  ...FEATURE_DEFINITIONS_1,
  ...FEATURE_DEFINITIONS_2,
  ...FEATURE_DEFINITIONS_3,
  ...FEATURE_DEFINITIONS_4,
  ...FEATURE_DEFINITIONS_5,
];

// Effective switch as the console sees it: stored and parent installed (mirrors `configuration_feature_enabled`; the server still decides).
export function capabilityOn(
  makerspace: { enabled_modules?: string[]; enabled_features?: string[] } | undefined, key: string,
) {
  // Decision 319: a retired switch reads off however it is stored (twin of capability_definitions.RETIRED_FEATURES).
  if (RETIRED_FEATURES.has(key) || !makerspace?.enabled_features?.includes(key)) return false;
  // Decision 254: the Inventory switch is the master of its children (twin of loan_visibility.LOAN_FEATURES).
  if (INVENTORY_CHILD_FEATURES.has(key) && !makerspace.enabled_features.includes("loans.enabled")) return false;
  const parent = FEATURE_DEFINITIONS.find(feature => feature.key === key)?.parent_module;
  return !parent || (makerspace.enabled_modules ?? []).includes(parent);
}
