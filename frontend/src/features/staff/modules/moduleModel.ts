import { t } from "@lingui/core/macro";
import { FEATURE_DEFINITIONS, INVENTORY_CHILD_FEATURES, isSecurityFeature } from "../../../lib/features";
import { featureHelp } from "../../../lib/featureHelp";
import { RETIRED_FEATURES } from "../../../lib/retiredFeatures";
import type { ModuleGroup, ModuleRow, LockReason } from "../ModuleSettingsRows";
import { roleUsesModule, runsWholeSpace, type RoleLike } from "./moduleRoleMap";

export type FeatureNeed = { kind: "module" | "feature"; key: string; label: string };
/** The modules route's canonical direct prerequisites per feature (`feature_requirements`). */
export type FeatureRequirements = Readonly<Record<string, { modules: string[]; features: string[] }>>;
export type FeatureModel = {
  key: string; label: string; help?: string; on: boolean; needs: FeatureNeed | null; lock?: "not_shipped" | null;
  /** Every module and feature this one needs, transitively (from `FeatureRequirements` plus the Inventory master). */
  requiresModules: string[]; requiresFeatures: string[];
};
export type CardModel = {
  key: string; label: string; description: string; areaKey: string; row: ModuleRow | null; features: FeatureModel[];
  on: boolean; lock: LockReason | null;
};
export type AreaModel = { key: string; label: string; description: string; alwaysOn: boolean; cards: CardModel[] };
export type StateFilter = "all" | "on" | "off" | "locked" | "changed";

const INVENTORY_MASTER = "loans.enabled";
const GENERAL = "general";

/** A module row's lock, as shown: a limit only locks while the module is off (it can always be switched off). */
export function lockOf(row: ModuleRow): LockReason | null {
  const reason = row.lock_reason ?? (row.core ? "core" : !row.available ? "not_shipped"
    : !row.installed && row.install_requires_superadmin ? "limit" : null);
  return reason === "limit" && row.installed ? null : reason;
}

const FEATURE_LABELS = new Map(FEATURE_DEFINITIONS.map(feature => [feature.key, feature.label]));

/**
 * Everything `key` needs, transitively: modules and features. Uses the server's canonical requirements when the
 * route sends them (an older server: the parent module only), plus the Inventory master switch of decision 254.
 */
export function prerequisites(key: string, requirements: FeatureRequirements) {
  const modules = new Set<string>(), features = new Set<string>();
  const visit = (current: string) => {
    const parent = FEATURE_DEFINITIONS.find(feature => feature.key === current)?.parent_module;
    const direct = requirements[current] ?? { modules: parent ? [parent] : [], features: [] };
    direct.modules.forEach(module => modules.add(module));
    for (const feature of [...direct.features, ...(INVENTORY_CHILD_FEATURES.has(current) ? [INVENTORY_MASTER] : [])]) {
      if (feature !== key && !features.has(feature)) { features.add(feature); visit(feature); }
    }
  };
  visit(key);
  return { modules: [...modules], features: [...features] };
}

function featureModels(parent: string | null, areaOn: Set<string>, labels: Map<string, string>, enabled: Set<string>, pick: (key: string) => boolean,
  locks: Readonly<Record<string, "not_shipped">> = {}, requirements: FeatureRequirements = {}, parentKnown = true) {
  return FEATURE_DEFINITIONS.filter(feature => !isSecurityFeature(feature.key) && !RETIRED_FEATURES.has(feature.key)
    && feature.parent_module === parent && pick(feature.key)).map<FeatureModel>(feature => {
    const { modules, features } = prerequisites(feature.key, requirements);
    // A parent this screen does not list (a virtual "General" row) cannot be offered, so it is not a need.
    const missingModule = modules.find(module => !areaOn.has(module) && (parentKnown || module !== feature.parent_module));
    const missingFeature = features.find(key => !enabled.has(key));
    const needs: FeatureNeed | null = missingModule ? { kind: "module", key: missingModule, label: labels.get(missingModule) ?? missingModule }
      : missingFeature ? { kind: "feature", key: missingFeature, label: missingFeature === INVENTORY_MASTER ? t`Inventory` : FEATURE_LABELS.get(missingFeature) ?? missingFeature } : null;
    return { key: feature.key, label: feature.label, help: featureHelp(feature.key), on: enabled.has(feature.key), needs, lock: locks[feature.key] ?? null,
      requiresModules: parentKnown ? modules : modules.filter(module => module !== feature.parent_module), requiresFeatures: features };
  });
}

/** Groups from the modules route plus the feature mirror, one card per module and a virtual card for parentless features. */
export function buildAreas(groups: ModuleGroup[], enabledFeatures: readonly string[], locks: Readonly<Record<string, "not_shipped">> = {},
  requirements: FeatureRequirements = {}): AreaModel[] {
  const enabled = new Set(enabledFeatures);
  const on = new Set(groups.flatMap(group => group.modules).filter(row => row.installed).map(row => row.key));
  const labels = new Map(groups.flatMap(group => group.modules).map(row => [row.key, row.label]));
  const known = new Set(labels.keys());
  const areas = groups.map<AreaModel>(group => ({
    key: group.key, label: group.label, description: group.description, alwaysOn: group.always_on,
    cards: group.modules.map<CardModel>(row => ({
      key: row.key, label: row.label, description: row.description, areaKey: group.key, row, on: row.installed, lock: lockOf(row),
      features: featureModels(row.key, on, labels, enabled, () => true, locks, requirements),
    })),
  }));
  const virtual = (key: string, label: string, areaKey: string, features: FeatureModel[]): CardModel => ({
    key, label, description: "", areaKey, row: null, features, on: true, lock: "core" });
  const inventory = featureModels(null, on, labels, enabled, key => key.startsWith("inventory.") || key.startsWith("loans."), locks, requirements);
  const unlisted = [...new Set(FEATURE_DEFINITIONS.map(feature => feature.parent_module).filter((key): key is string => !!key && !known.has(key)))];
  const general = [...featureModels(null, on, labels, enabled, key => !key.startsWith("inventory.") && !key.startsWith("loans."), locks, requirements),
    ...unlisted.flatMap(parent => featureModels(parent, on, labels, enabled, () => true, locks, requirements, false))];
  const home = areas.find(area => area.key === "inventory");
  if (home && inventory.length) home.cards.push(virtual("inventory", t`Inventory features`, home.key, inventory));
  if (general.length) areas.push({ key: GENERAL, label: t`General`, description: t`Features that do not belong to one area.`, alwaysOn: true,
    cards: [virtual(GENERAL, t`General features`, GENERAL, general)] });
  return areas;
}

export const cardState = (card: CardModel): "on" | "off" | "locked" => card.lock === "core" || card.lock === "not_shipped" || (card.lock === "limit" && !card.on) ? "locked" : card.on ? "on" : "off";

export function matches(card: CardModel, query: string, filter: StateFilter, touched: ReadonlySet<string>): { show: boolean; viaFeature: boolean } {
  const q = query.trim().toLowerCase();
  const hay = (text: string) => text.toLowerCase().includes(q);
  const direct = !q || hay(card.label) || hay(card.key) || hay(card.description);
  const viaFeature = !!q && !direct && card.features.some(feature => hay(feature.label) || hay(feature.key) || hay(feature.help ?? ""));
  const state = cardState(card);
  const stateOk = filter === "all" || filter === state || (filter === "changed" && (touched.has(card.key) || card.features.some(feature => touched.has(feature.key))))
    || (filter === "off" && !card.on);
  return { show: (direct || viaFeature) && stateOk, viaFeature };
}

export function areasForRole(areas: AreaModel[], role: RoleLike): AreaModel[] {
  return areas.map(area => ({ ...area, cards: area.cards.filter(card => card.row ? roleUsesModule(role, card.key) : runsWholeSpace(role)) }))
    .filter(area => area.cards.length > 0);
}

/** Modules the role uses, counted against every switchable module, for the role summary line. */
export const roleUsage = (areas: AreaModel[], role: RoleLike) => {
  const rows = areas.flatMap(area => area.cards).filter(card => card.row);
  return { used: rows.filter(card => roleUsesModule(role, card.key)).length, total: rows.length };
};
