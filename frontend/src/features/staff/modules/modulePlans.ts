import { t } from "@lingui/core/macro";
import type { AreaModel, CardModel, FeatureModel } from "./moduleModel";

export type Step =
  | { kind: "module"; key: string; action: "install" | "uninstall"; restore?: string[] }
  | { kind: "features"; add?: string[]; remove?: string[] };
export type Confirm = { title: string; message: string; lines: string[]; confirmLabel: string; tone?: "danger" };
export type Plan = { steps: Step[]; confirm: Confirm | null; summary: string; touched: string[] };

const cards = (areas: AreaModel[]) => areas.flatMap(area => area.cards);
const find = (areas: AreaModel[], key: string) => cards(areas).find(card => card.key === key && card.row);
const labelOf = (areas: AreaModel[], key: string) => find(areas, key)?.label ?? key;
// A not-shipped feature (decision 329) cannot be turned back on, so an undo never tries to restore it.
const onFeatures = (card: CardModel) => card.features.filter(feature => feature.on && !feature.lock).map(feature => feature.key);
const allFeatures = (areas: AreaModel[]) => cards(areas).flatMap(card => card.features);
const installed = (areas: AreaModel[]) => new Set(cards(areas).filter(card => card.row && card.on).map(card => card.key));
const featureLabel = (areas: AreaModel[], key: string) => allFeatures(areas).find(feature => feature.key === key)?.label ?? key;
/** Switched-on features elsewhere that need module `key`: the server drops them with it (`prune_features`). */
const featuresNeedingModule = (areas: AreaModel[], key: string, card: CardModel) => allFeatures(areas)
  .filter(feature => feature.on && !feature.lock && feature.requiresModules.includes(key) && !card.features.includes(feature));
/**
 * Switched-on features that need `key` (transitively): the server refuses to drop `key` while they stay on.
 * The Inventory master is not a canonical requirement (decision 254): its children stay stored and only hide.
 */
export const dependentFeatures = (areas: AreaModel[], key: string) => key === "loans.enabled" ? []
  : allFeatures(areas).filter(feature => feature.on && feature.key !== key && feature.requiresFeatures.includes(key));

/** Keys that must be switched off before `key`, dependents first (the server refuses to remove a depended-on module). */
export function offOrder(areas: AreaModel[], roots: string[]): string[] {
  const out: string[] = [];
  const seen = new Set<string>();
  const visit = (key: string) => {
    if (seen.has(key)) return;
    seen.add(key);
    for (const dependent of find(areas, key)?.row?.required_by ?? []) visit(dependent);
    out.push(key);
  };
  roots.forEach(visit);
  return out;
}

const uninstallStep = (areas: AreaModel[], key: string): Step => {
  const card = find(areas, key);
  return { kind: "module", key, action: "uninstall",
    restore: card ? [...onFeatures(card), ...featuresNeedingModule(areas, key, card).map(feature => feature.key)] : [] };
};

export function planModule(areas: AreaModel[], card: CardModel, turnOn: boolean): Plan {
  const row = card.row!;
  if (turnOn) {
    const extra = row.pulls_in;
    return { steps: [{ kind: "module", key: card.key, action: "install" }], touched: [card.key, ...extra], summary: t`${card.label} switched on.`,
      confirm: extra.length ? { title: t`Switch on ${card.label}?`, message: t`${card.label} needs other areas, which will be switched on with it.`,
        lines: extra.map(key => labelOf(areas, key)), confirmLabel: t`Switch on` } : null };
  }
  const order = offOrder(areas, [card.key]);
  const dependents = order.filter(key => key !== card.key);
  const elsewhere = order.flatMap(key => { const owner = find(areas, key); return owner ? featuresNeedingModule(areas, key, owner) : []; });
  const hidden = [...onFeatures(card), ...elsewhere.map(feature => feature.key)];
  const lines = [...dependents.map(key => t`${labelOf(areas, key)} (needs ${card.label})`),
    ...card.features.filter(feature => feature.on).map(feature => feature.label), ...new Set(elsewhere.map(feature => feature.label))];
  return { steps: order.map(key => uninstallStep(areas, key)), touched: order, summary: t`${card.label} switched off.`,
    confirm: dependents.length || hidden.length ? { title: t`Switch off ${card.label}?`, confirmLabel: t`Switch off`,
      message: dependents.length ? t`${card.label} is needed by other areas, which switch off with it. Their features are hidden too. Nothing is deleted.`
        : t`These features are hidden while ${card.label} is off. Nothing is deleted.`, lines } : null };
}

export function planFeature(areas: AreaModel[], feature: FeatureModel, turnOn: boolean): Plan {
  const summary = turnOn ? t`${feature.label} switched on.` : t`${feature.label} switched off.`;
  if (!turnOn) {
    // Dependents go first, in the same save: the server refuses a list that keeps a feature without its prerequisite.
    const dependents = dependentFeatures(areas, feature.key);
    const remove = [...dependents.map(row => row.key), feature.key];
    if (feature.key === "loans.enabled") {
      return { steps: [{ kind: "features", remove }], touched: remove, summary,
        confirm: { title: t`Switch off Inventory?`, confirmLabel: t`Switch off`, lines: dependents.map(row => row.label),
          message: t`Borrowing, self-checkout, the kiosk and the other Inventory features are hidden. Nothing is deleted.` } };
    }
    return { steps: [{ kind: "features", remove }], touched: remove, summary,
      confirm: dependents.length ? { title: t`Switch off ${feature.label}?`, confirmLabel: t`Switch off`, lines: dependents.map(row => row.label),
        message: t`These features need ${feature.label}, so they switch off with it. Nothing is deleted.` } : null };
  }
  // Every missing prerequisite, transitively: modules install first (each pulls in its own modules), then one save adds the features.
  const on = installed(areas);
  const enabled = new Set(allFeatures(areas).filter(row => row.on).map(row => row.key));
  const modules = feature.requiresModules.filter(key => !on.has(key) && find(areas, key));
  const features = feature.requiresFeatures.filter(key => !enabled.has(key));
  const add = [...features, feature.key];
  const steps: Step[] = [...modules.map<Step>(key => ({ kind: "module", key, action: "install" })), { kind: "features", add }];
  const touched = [...modules, ...add];
  const pulled = [...new Set(modules.flatMap(key => find(areas, key)?.row?.pulls_in ?? []))].filter(key => !modules.includes(key));
  const extra = [...modules.map(key => labelOf(areas, key)), ...features.map(key => featureLabel(areas, key))];
  if (modules.length === 1 && !features.length) {
    const label = labelOf(areas, modules[0]);
    return { steps, touched, summary, confirm: { title: t`Switch on ${label} too?`, confirmLabel: t`Switch on both`,
      message: t`${feature.label} only works while ${label} is on. Switch both on?`, lines: pulled.map(key => labelOf(areas, key)) } };
  }
  // Only the Inventory master is missing: switching it on is implied (decision 254), as before.
  if (!modules.length && (!features.length || (features.length === 1 && features[0] === "loans.enabled"))) {
    return { steps, touched, summary, confirm: null };
  }
  return { steps, touched, summary, confirm: { title: t`Switch on ${feature.label}?`, confirmLabel: t`Switch all on`,
    message: t`${feature.label} needs these too. They switch on with it.`, lines: [...extra, ...pulled.map(key => labelOf(areas, key))] } };
}

export function planArea(areas: AreaModel[], area: AreaModel, turnOn: boolean): Plan {
  const open = area.cards.filter(card => card.row && !card.lock);
  const keys = open.filter(card => card.on !== turnOn).map(card => card.key);
  const skipped = area.cards.filter(card => card.row && card.lock && card.on !== turnOn).length;
  const ordered = turnOn ? keys : offOrder(areas, keys).filter(key => find(areas, key)?.on);
  const steps: Step[] = ordered.map(key => turnOn ? { kind: "module", key, action: "install" } : uninstallStep(areas, key));
  const lines = ordered.map(key => labelOf(areas, key));
  const label = area.label;
  const count = ordered.length;
  return { steps, touched: ordered, summary: turnOn ? t`${label}: ${count} switched on.` : t`${label}: ${count} switched off.`,
    confirm: { title: turnOn ? t`Switch on everything in ${label}?` : t`Switch off everything in ${label}?`, confirmLabel: turnOn ? t`Switch all on` : t`Switch all off`,
      message: (turnOn ? t`These switch on.` : t`These switch off and their features are hidden. Nothing is deleted.`) + (skipped ? ` ${t`${skipped} locked switches stay as they are.`}` : ""),
      lines } };
}

/** The steps that undo `steps`, in reverse; switching a module back on also restores the features it had. */
export function inverse(steps: Step[]): Step[] {
  return [...steps].reverse().flatMap<Step>(step => {
    if (step.kind === "features") return [{ kind: "features", add: step.remove, remove: step.add }];
    if (step.action === "install") return [{ kind: "module", key: step.key, action: "uninstall" }];
    return [{ kind: "module", key: step.key, action: "install" }, ...(step.restore?.length ? [{ kind: "features", add: step.restore } as Step] : [])];
  });
}
