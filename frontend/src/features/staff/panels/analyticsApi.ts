import { useQuery } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";
import type { ReportCatalog } from "./operationsReportsConfig";
import type { ChartRecord } from "./charts/chartSpec";

/** Local serializer contracts until the coordinator regenerates OpenAPI. */
export type ReportChartSpec = {
  series: string[]; x: { field: string; kind: "time" | "category" };
  values: { field: string; unit: string }[];
  currency_field: string | null; partition: "tenant" | "currency" | "unit" | null;
  negatives: "allow" | "clip"; truncation: { top_n: number; other_label: string } | null;
  alt_template: string;
};
export type AnalyticsReport = {
  report_key?: string; rows?: unknown[][]; typed_rows?: ChartRecord[];
  meta?: Record<string, unknown>;
} & Record<string, unknown>;
export type DashboardWidget = {
  key: string; title: string; required_action: string; required_modules: string[];
  kind: "count" | "trend" | "top_n" | "heatmap" | "queue";
  report_keys: string[]; default_period: number; data: AnalyticsReport; chart_spec: ReportChartSpec | null;
};
export type DashboardAnalytics = {
  widgets?: DashboardWidget[];
  queue_tiles?: { ready_to_issue?: number; due_returns?: number; pickups?: number };
  outstanding_by_currency?: Record<string, string>;
};
export type AnalyticsPeriod = { start: string; end: string; grain: string };
export function periodParams({ start, end, grain }: AnalyticsPeriod, grains?: string[]) {
  const params = new URLSearchParams();
  if (start) params.set("start", start);
  if (end) params.set("end", end);
  if (grains === undefined || grains.length) params.set("grain", grains?.includes(grain) ? grain : grains?.[0] ?? grain);
  return params;
}
export function useAnalyticsCatalog(makerspaceId: number, enabled = true) {
  return useQuery({ queryKey: ["report-catalog", makerspaceId], enabled,
    queryFn: () => staffRequest<ReportCatalog>(`/admin/makerspace/${makerspaceId}/reports/catalog`) });
}
export function useAnalyticsReport(base: string, key: string, params: URLSearchParams, enabled = true) {
  return useQuery({ queryKey: ["operations-report", "analytics-panel", base, key, params.toString()], enabled, retry: false,
    queryFn: () => staffRequest<AnalyticsReport>(`${base}/${encodeURIComponent(key)}?${params}`) });
}
/** Matrix headers are wire names, never inferred from a report key. Summary is a flat object. */
export function analyticsRows(data?: AnalyticsReport): ChartRecord[] {
  if (!data) return [];
  if (data.typed_rows) return data.typed_rows;
  if (data.rows) {
    const [headers = [], ...rows] = data.rows;
    return rows.map(row => Object.fromEntries(headers.map((key, index) => [String(key), row[index]])));
  }
  return Object.keys(data).length ? [data] : [];
}
