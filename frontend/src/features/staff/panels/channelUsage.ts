import type { ChartRecord } from "./charts/chartSpec";
import type { ReportChartSpec } from "./analyticsApi";

/** Pure projections of the "Web and app use" report rows (measure x channel x area x period). */
export const CHANNEL_ORDER = ["web", "ios", "android", "api_client"] as const;
export const SESSION_DAYS = "session_days";
export const API_CALLS = "api_calls";

const num = (value: unknown) => Number.isFinite(Number(value)) ? Number(value) : 0;
const bump = (map: Map<string, number>, key: string, by: number) => map.set(key, (map.get(key) ?? 0) + by);
const rank = (channel: string) => {
  const at = CHANNEL_ORDER.indexOf(channel as typeof CHANNEL_ORDER[number]);
  return at < 0 ? CHANNEL_ORDER.length : at;
};

export const TREND_SPEC: ReportChartSpec = {
  series: ["channel"], x: { field: "period", kind: "time" }, values: [{ field: "value", unit: "session-days" }],
  currency_field: null, partition: null, negatives: "clip", truncation: null, alt_template: "{value} session-days in {period}",
};

/** Totals and share per channel for one measure, in the fixed web, iOS, Android, API order. */
export function channelTotals(rows: readonly ChartRecord[], measure: string) {
  const totals = new Map<string, number>();
  for (const row of rows) if (row.measure === measure) bump(totals, String(row.channel), num(row.value));
  const sum = [...totals.values()].reduce((a, b) => a + b, 0);
  return [...totals].sort(([a], [b]) => rank(a) - rank(b))
    .map(([channel, total]) => ({ channel, total, share: sum ? Math.round(total / sum * 1000) / 10 : 0 }));
}

/** One point per period and channel, so the trend chart draws one line per channel. */
export function trendRows(rows: readonly ChartRecord[], measure = SESSION_DAYS): ChartRecord[] {
  const sums = new Map<string, number>();
  for (const row of rows) if (row.measure === measure) bump(sums, `${row.period}|${row.channel}`, num(row.value));
  return [...sums].map(([key, value]) => {
    const [period, channel] = key.split("|");
    return { period, channel, value };
  }).sort((a, b) => a.period.localeCompare(b.period));
}

export type SpaceChannelRow = { id: string; name: string; values: Record<string, number>; total: number };
/** One row per makerspace (null = unattributed deployment activity) with session-days per channel. */
export function perSpace(rows: readonly ChartRecord[], name: (id: number | null) => string): SpaceChannelRow[] {
  const bySpace = new Map<string, SpaceChannelRow>();
  for (const row of rows) {
    if (row.measure !== SESSION_DAYS || !("makerspace_id" in row)) continue;
    const id = row.makerspace_id == null ? null : Number(row.makerspace_id);
    const entry = bySpace.get(String(id)) ?? { id: String(id), name: name(id), values: {}, total: 0 };
    entry.values[String(row.channel)] = (entry.values[String(row.channel)] ?? 0) + num(row.value);
    entry.total += num(row.value);
    bySpace.set(String(id), entry);
  }
  return [...bySpace.values()].sort((a, b) => b.total - a.total || a.name.localeCompare(b.name));
}

/** The busiest areas (features) per channel by authenticated calls. */
export function topAreas(rows: readonly ChartRecord[], limit = 5) {
  const byChannel = new Map<string, Map<string, number>>();
  for (const row of rows) {
    if (row.measure !== API_CALLS) continue;
    const areas = byChannel.get(String(row.channel)) ?? new Map<string, number>();
    bump(areas, String(row.area), num(row.value));
    byChannel.set(String(row.channel), areas);
  }
  return [...byChannel].sort(([a], [b]) => rank(a) - rank(b)).map(([channel, areas]) => ({
    channel, areas: [...areas].sort((a, b) => b[1] - a[1]).slice(0, limit).map(([area, value]) => ({ area, value })),
  }));
}

/** Distinct, new and returning active people per channel (computed on the server; counts only). */
export function accountTotals(rows: readonly ChartRecord[]) {
  const by = new Map<string, { active: number; fresh: number; returning: number }>();
  for (const row of rows) {
    const entry = by.get(String(row.channel)) ?? { active: 0, fresh: 0, returning: 0 };
    if (row.measure === "active_accounts") entry.active += num(row.value);
    if (row.measure === "new_accounts") entry.fresh += num(row.value);
    if (row.measure === "returning_accounts") entry.returning += num(row.value);
    by.set(String(row.channel), entry);
  }
  return [...by].filter(([, v]) => v.active).sort(([a], [b]) => rank(a) - rank(b)).map(([channel, v]) => ({ channel, ...v }));
}

/** Each key flow with its completions per channel and every channel's share of that flow. */
export function flowShares(rows: readonly ChartRecord[]) {
  const flows = new Map<string, Map<string, number>>();
  for (const row of rows) {
    if (row.measure !== "flow_completions") continue;
    const channels = flows.get(String(row.area)) ?? new Map<string, number>();
    bump(channels, String(row.channel), num(row.value));
    flows.set(String(row.area), channels);
  }
  return [...flows].map(([flow, channels]) => {
    const sum = [...channels.values()].reduce((a, b) => a + b, 0);
    return { flow, total: sum, channels: [...channels].sort(([a], [b]) => rank(a) - rank(b))
      .map(([channel, value]) => ({ channel, value, share: sum ? Math.round(value / sum * 1000) / 10 : 0 })) };
  }).sort((a, b) => b.total - a.total);
}

/** App builds per phone platform (distinct installs), busiest first. */
export function appVersions(rows: readonly ChartRecord[]) {
  const by = new Map<string, Map<string, number>>();
  for (const row of rows) {
    if (row.measure !== "app_versions") continue;
    const versions = by.get(String(row.channel)) ?? new Map<string, number>();
    bump(versions, String(row.area), num(row.value));
    by.set(String(row.channel), versions);
  }
  return [...by].sort(([a], [b]) => rank(a) - rank(b)).map(([channel, versions]) => {
    const sum = [...versions.values()].reduce((a, b) => a + b, 0);
    return { channel, versions: [...versions].sort((a, b) => b[1] - a[1]).map(([version, value]) => ({ version, value, share: sum ? Math.round(value / sum * 1000) / 10 : 0 })) };
  });
}

/** Rows of one makerspace for the superadmin drill-down; null selects every space. */
export function forSpace(rows: readonly ChartRecord[], id: number | null): ChartRecord[] {
  return id == null ? [...rows] : rows.filter(row => row.makerspace_id === id);
}

const FIELDS = ["period", "measure", "channel", "area", "value", "share_percent"] as const;
/** The report rows as CSV, with a leading space column when present. Counts only. */
export function channelCsv(rows: readonly ChartRecord[]): string {
  const withSpace = rows.some(row => "makerspace_id" in row);
  const header = withSpace ? ["makerspace_id", ...FIELDS] : [...FIELDS];
  const cell = (value: unknown) => value == null ? "" : /[",\n]/.test(String(value)) ? `"${String(value).replace(/"/g, '""')}"` : String(value);
  return [header, ...rows.map(row => header.map(field => row[field]))].map(line => line.map(cell).join(",")).join("\n");
}
