import { t } from "@lingui/core/macro";
import type { LimitArea, LimitLevel, LimitSource, SpaceLimits } from "./limitsApi";

/**
 * One shape for every limit row the server sends (decisions 234, 281, 284): the fair-use `rows`
 * (effective + override + source), and the monthly `platform_rows` / `quota_rows` (limit + level).
 * The screen renders whatever keys arrive, grouped by the row's `area`, so a key added on the server
 * later appears without a frontend change.
 */
export type UnifiedLimit = {
  /** `count`, `bytes`, `amount` (whole currency units, per currency), `per_minute` (a rate: no usage) or a later unit. */
  key: string; label: string; area: string; unit: string;
  /** What applies now; null = no limit. */
  limit: number | null; used: number | null; percent: number | null; level: LimitLevel;
  /** The value stored for this space (what the input edits); undefined = none stored. */
  stored: number | undefined;
  source?: LimitSource; suggested?: number | null;
  /** The platform-wide default for this key (decision 328a), null = none. */
  platformDefault?: number | null;
  /** False for a plan's own monthly allowance, which only the plan sets. */
  editable: boolean;
};
export type LimitGroup = { key: string; label: string; rows: UnifiedLimit[] };

export const WARNING_PERCENT = 80;
const MB = 1048576;

export function levelOf(percent: number | null): LimitLevel {
  if (percent === null) return "ok";
  return percent >= 100 ? "limit" : percent >= WARNING_PERCENT ? "warning" : "ok";
}

export function percentOf(used: number | null, limit: number | null): number | null {
  if (used === null || limit === null) return null;
  if (limit <= 0) return 100;
  return Math.round(used * 1000 / limit) / 10;
}

/** Group names when the server sends no `areas` (older payloads); a function so they follow the language. */
const AREA_FALLBACK = (): Record<string, string> => ({
  people: t`People`, inventory: t`Inventory`, machines: t`Machines`, events: t`Events`, bookings: t`Bookings`,
  shop: t`Shop`, money: t`Money`, messaging: t`Messaging`, integrations: t`Integrations`, storage: t`Storage`, other: t`Other`,
});

export function unifyLimits(data: SpaceLimits): UnifiedLimit[] {
  const seen = new Set<string>();
  const out: UnifiedLimit[] = [];
  // Monthly rows first: a key the server sends in both lists (e.g. a plan's events_monthly) keeps the editable one.
  for (const row of [...(data.quota_rows ?? []), ...(data.platform_rows ?? [])]) {
    if (seen.has(row.key)) continue;
    seen.add(row.key);
    const percent = row.percent ?? percentOf(row.used, row.limit);
    out.push({ key: row.key, label: row.label, area: row.group || row.area || "other", unit: row.unit, limit: row.limit, used: row.used,
      percent, level: row.level ?? levelOf(percent), stored: row.limit === null ? undefined : row.limit, editable: true,
      platformDefault: row.platform_default });
  }
  for (const row of data.rows ?? []) {
    if (seen.has(row.key)) continue;
    seen.add(row.key);
    const percent = percentOf(row.used, row.effective);
    out.push({ key: row.key, label: row.label, area: row.group || row.area || "other", unit: row.unit, limit: row.effective, used: row.used,
      percent, level: levelOf(percent), stored: row.has_override ? row.override ?? -1 : undefined, source: row.source,
      suggested: row.suggested, platformDefault: row.platform_default, editable: !(row.key.endsWith("_monthly") && row.source === "plan" && !row.has_override) });
  }
  return out;
}

/** Rows grouped in the server's area order; areas with no rows are left out, unknown areas go last. */
export function groupLimits(rows: UnifiedLimit[], areas: LimitArea[] | undefined): LimitGroup[] {
  const fallback = AREA_FALLBACK();
  const order: LimitArea[] = [...(areas ?? Object.entries(fallback).map(([key, label]) => ({ key, label })))];
  for (const row of rows) if (!order.some(area => area.key === row.area)) order.push({ key: row.area, label: fallback[row.area] ?? row.area });
  return order.map(area => ({ ...area, rows: rows.filter(row => row.area === area.key) })).filter(group => group.rows.length);
}

/** Inputs are shown in MB for byte limits; everything else is a whole number. */
export const toInput = (row: Pick<UnifiedLimit, "unit">, value: number | undefined) =>
  value === undefined ? "" : value === -1 ? "-1" : row.unit === "bytes" ? String(Math.round(value / MB)) : String(value);
export const fromInput = (row: Pick<UnifiedLimit, "unit">, text: string) => {
  const value = Number(text.trim());
  return value === -1 || row.unit !== "bytes" ? value : value * MB;
};
export const validInput = (text: string) => text.trim() === "" || /^(-1|\d+)$/.test(text.trim());

/**
 * The COMPLETE override map the PUT expects: every stored value, with the edited drafts applied
 * (blank = no limit, i.e. the key is removed). `custom_domain` rides along as the one boolean.
 */
export function buildOverrides(rows: UnifiedLimit[], drafts: Record<string, string>, customDomain: boolean) {
  const overrides: Record<string, number | boolean> = {};
  for (const row of rows) {
    const text = drafts[row.key];
    if (text === undefined) { if (row.stored !== undefined) overrides[row.key] = row.stored; continue; }
    if (text.trim() !== "") overrides[row.key] = fromInput(row, text);
  }
  if (customDomain) overrides.custom_domain = true;
  return overrides;
}
