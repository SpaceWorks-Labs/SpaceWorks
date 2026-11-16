import { useQuery } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";
import type { ReportCatalog } from "./operationsReportsConfig";
import type { ChartRecord } from "./charts/chartSpec";

import type { AnalyticsReportResponse, DashboardWidget, GenericAnalyticsReport } from "../../../generated/api";
export type { ReportChartSpec, DashboardWidget } from "../../../generated/api";
export type { Dashboard as DashboardAnalytics } from "../../../generated/api";
export type AnalyticsReport = AnalyticsReportResponse;
// UI filter state; this is not a backend serializer DTO.
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
export function analyticsRows(data?: AnalyticsReport | DashboardWidget["data"]): ChartRecord[] {
  if (!data) return [];
  // Widget data is untyped JSON in OpenAPI; project its report envelope for chart rendering.
  const report = data as Partial<GenericAnalyticsReport>;
  if (report.typed_rows) return report.typed_rows;
  if (report.rows) {
    const [headers = [], ...rows] = report.rows;
    return rows.map(row => Object.fromEntries(headers.map((key, index) => [String(key), row[index]])));
  }
  return Object.keys(data).length ? [data] : [];
}

export function analyticsMeta(data?: AnalyticsReport | DashboardWidget["data"]): GenericAnalyticsReport["meta"] {
  if (!data || !("meta" in data)) return undefined;
  const meta = data.meta;
  return meta && typeof meta === "object" && !Array.isArray(meta) ? meta as Record<string, unknown> : undefined;
}
