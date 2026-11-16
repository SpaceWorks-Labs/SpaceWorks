import { t } from "@lingui/core/macro";

import type { ConsumableDefinition, ConsumableInput } from "./consumablesApi";
import { poolUnitFor, productUnit, type ConsumableKind, type ConsumableUnit, type EstimateBy, type ProfileAttributes, type RecordBy } from "./profileUnits";

export type ProfileDraft = {
  key: string; name: string; kind: ConsumableKind; unit: ConsumableUnit; attributes: ProfileAttributes; required: boolean;
  estimate_by: EstimateBy; record_by: RecordBy[]; unit_price: string; consumable_pool: number | null; product: number | null; is_active: boolean;
};

export const blankDraft = (): ProfileDraft => ({ key: "", name: "", kind: "material", unit: "g", attributes: {}, required: false,
  estimate_by: "none", record_by: ["staff"], unit_price: "", consumable_pool: null, product: null, is_active: true });

export const draftFromRow = (row: ConsumableDefinition): ProfileDraft => ({ key: row.key, name: row.name, kind: row.kind, unit: row.unit,
  attributes: row.attributes ?? {}, required: row.required, estimate_by: row.estimate_by, record_by: row.record_by, unit_price: row.unit_price ?? "",
  consumable_pool: row.consumable_pool, product: row.product, is_active: row.is_active });

/** A lowercase key the server accepts: `[a-z][a-z0-9_]{0,49}`, never ending in `_id`. */
export function keyFromName(name: string) {
  const key = name.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^[^a-z]+/, "").replace(/_+$/, "").slice(0, 50);
  return key.endsWith("_id") ? `${key}_x`.slice(0, 50) : key;
}

/** What still blocks saving a profile row, in words; empty when it can be sent. */
export function draftProblem(draft: ProfileDraft, isNew: boolean): string {
  if (!draft.name.trim()) return t`Give the consumable a name.`;
  if (isNew && (!/^[a-z][a-z0-9_]{0,49}$/.test(draft.key) || draft.key.endsWith("_id"))) return t`The key starts with a letter and uses only lowercase letters, digits and underscores.`;
  if (!draft.record_by.length) return t`Choose who records the amount used.`;
  if (draft.unit_price.trim() && !(Number(draft.unit_price) >= 0)) return t`The price per unit must be zero or more.`;
  if (draft.consumable_pool !== null && draft.product !== null) return t`Link a stock pool or a product, not both.`;
  if (draft.product !== null && !productUnit(draft.unit)) return t`A product can only be linked when the unit is sheets, pieces or uses.`;
  return "";
}

/** The unit changed: a stock link that no longer matches the new unit is dropped. */
export function withUnit(draft: ProfileDraft, unit: ConsumableUnit, poolUnit?: (poolId: number) => string | undefined): ProfileDraft {
  const poolMismatch = draft.consumable_pool !== null && poolUnit?.(draft.consumable_pool) !== poolUnitFor(unit);
  return { ...draft, unit, consumable_pool: poolMismatch ? null : draft.consumable_pool, product: productUnit(unit) ? draft.product : null };
}

export const draftBody = (draft: ProfileDraft, position: number): ConsumableInput => ({ key: draft.key, name: draft.name.trim(), kind: draft.kind,
  unit: draft.unit, attributes: draft.attributes, required: draft.required, estimate_by: draft.estimate_by, record_by: draft.record_by,
  unit_price: draft.unit_price.trim() || null, consumable_pool: draft.consumable_pool, product: draft.product, position, is_active: draft.is_active });
