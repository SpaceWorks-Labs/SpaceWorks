import { t } from "@lingui/core/macro";

export type ConsumableKind = "material" | "tool_wear" | "time" | "per_job" | "other";
export type ConsumableUnit = "g" | "kg" | "mm" | "m" | "ml" | "l" | "cm2" | "m2" | "cm3" | "sheet" | "piece" | "min" | "h" | "use" | "k_stitch";
export type EstimateBy = "none" | "member" | "staff" | "file";
export type RecordBy = "staff" | "member" | "adapter";
export type AttributeKey = "material" | "colour" | "thickness" | "size";
export type ProfileAttributes = Partial<Record<AttributeKey, string[]>>;
export type PoolUnit = "grams" | "milliliters" | "millimeters" | "count";

export const KINDS = (): [ConsumableKind, string][] => [["material", t`Material`], ["tool_wear", t`Tool wear`], ["time", t`Time`], ["per_job", t`Per job`], ["other", t`Other`]];
export const UNITS = (): [ConsumableUnit, string][] => [["g", t`Grams (g)`], ["kg", t`Kilograms (kg)`], ["mm", t`Millimetres (mm)`], ["m", t`Metres (m)`],
  ["ml", t`Millilitres (ml)`], ["l", t`Litres (l)`], ["cm2", t`Square cm (cm2)`], ["m2", t`Square metres (m2)`], ["cm3", t`Cubic cm (cm3)`],
  ["sheet", t`Sheets`], ["piece", t`Pieces`], ["min", t`Minutes`], ["h", t`Hours`], ["use", t`Uses`], ["k_stitch", t`Thousand stitches`]];
export const ESTIMATE_BY = (): [EstimateBy, string][] => [["none", t`Not estimated`], ["member", t`The member`], ["staff", t`Staff`], ["file", t`Read from the file`]];
export const RECORD_BY = (): [RecordBy, string][] => [["staff", t`Staff`], ["member", t`The member`], ["adapter", t`The machine adapter`]];
export const ATTRIBUTES = (): [AttributeKey, string][] => [["material", t`Material`], ["colour", t`Colour`], ["thickness", t`Thickness`], ["size", t`Size`]];

const POOL_UNIT: Record<ConsumableUnit, PoolUnit | null> = { g: "grams", kg: "grams", ml: "milliliters", l: "milliliters", cm3: "milliliters",
  mm: "millimeters", m: "millimeters", sheet: "count", piece: "count", use: "count", cm2: null, m2: null, min: null, h: null, k_stitch: null };

/** The stock-pool unit a profile unit may link to, or null when the unit cannot be tied to a pool. */
export const poolUnitFor = (unit: ConsumableUnit): PoolUnit | null => POOL_UNIT[unit];
/** Products are countable stock: only sheet, piece and use link to one. */
export const productUnit = (unit: ConsumableUnit) => unit === "sheet" || unit === "piece" || unit === "use";
/** Sheets, pieces and uses are counted whole; every other unit takes decimals. */
export const wholeUnit = productUnit;

export const unitLabel = (unit: ConsumableUnit) => UNITS().find(([value]) => value === unit)?.[1] ?? unit;
export { unitText as unitShort } from "../../../../machine-consumables/entries";
