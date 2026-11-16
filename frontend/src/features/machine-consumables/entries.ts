import { t } from "@lingui/core/macro";

/** What the member and staff forms need of one profile row (decision 341). A subset of the staff `ConsumableDefinition`. */
export type EntryRow = {
  key: string; name: string; unit: string; attributes: Partial<Record<"material" | "colour" | "thickness" | "size", string[]>>; required: boolean;
};
export type EntryValue = { quantity: string; attributes: Record<string, string> };
export type EntryValues = Record<string, EntryValue>;
export type ConsumableEntry = { key: string; quantity: string; attributes: Record<string, string> };

/** Sheets, pieces and uses are counted whole; every other unit takes decimals. */
export const WHOLE_UNITS = new Set(["sheet", "piece", "use"]);
export const isWhole = (unit: string) => WHOLE_UNITS.has(unit);
const SYMBOLS: Record<string, string> = { cm2: "cm²", m2: "m²", cm3: "cm³" };
export const unitText = (unit: string) => unit === "k_stitch" ? t`k stitches` : SYMBOLS[unit] ?? unit;

const quantityOf = (values: EntryValues, key: string) => (values[key]?.quantity ?? "").trim();

/** Why a typed amount is not acceptable, or empty. A blank amount is fine here: `required` is checked separately. */
export function quantityProblem(row: EntryRow, quantity: string): string {
  const text = quantity.trim();
  if (!text) return "";
  const value = Number(text);
  if (!Number.isFinite(value) || value <= 0) return t`Enter an amount above zero for ${row.name}.`;
  if (isWhole(row.unit) && !Number.isInteger(value)) return t`${row.name} is counted in whole numbers.`;
  return "";
}

/** What still blocks sending the entries, in words; empty when complete. `requiredOnly` skips the required-gate (estimates need none). */
export function entriesProblem(rows: EntryRow[], values: EntryValues, requireRequired = true): string {
  for (const row of rows) {
    const quantity = quantityOf(values, row.key);
    if (!quantity) { if (requireRequired && row.required) return t`Enter how much ${row.name} is needed.`; continue; }
    const bad = quantityProblem(row, quantity);
    if (bad) return bad;
    for (const [attribute, choices] of Object.entries(row.attributes)) {
      if (choices?.length && !values[row.key]?.attributes[attribute]) return t`Choose the ${attribute} for ${row.name}.`;
    }
  }
  return "";
}

/** The request entries: only rows with an amount, attributes without blanks. */
export function entriesPayload(rows: EntryRow[], values: EntryValues): ConsumableEntry[] {
  return rows.filter(row => quantityOf(values, row.key)).map(row => ({ key: row.key, quantity: quantityOf(values, row.key),
    attributes: Object.fromEntries(Object.entries(values[row.key]?.attributes ?? {}).filter(([, value]) => value.trim())) }));
}

/** Required rows that have no amount yet. */
export const missingRequired = (rows: EntryRow[], values: EntryValues) => rows.filter(row => row.required && !quantityOf(values, row.key));
