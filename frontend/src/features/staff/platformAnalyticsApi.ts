import { useQuery } from "@tanstack/react-query";
import { staffRequest } from "../../lib/api";
import { periodParams, type AnalyticsPeriod, type ReportChartSpec } from "./panels/analyticsApi";

import type { AnalyticsMakerspacePage, PlatformAnalyticsReport, ReportCatalog } from "../../generated/api";
export type { AnalyticsMakerspace, AnalyticsMakerspacePage, PlatformAnalyticsReport } from "../../generated/api";
export function usePlatformAnalytics(key: "platform-services" | "platform-usage", period: AnalyticsPeriod) {
  return useQuery({ queryKey: ["platform-analytics", key, period], retry: false,
    queryFn: () => staffRequest<PlatformAnalyticsReport>(`/admin/platform/analytics/${key}?${periodParams(period)}`) });
}
/** Every report that rolls up across makerspaces, each carrying its module group (the same grouping as the module switches). */
export function usePlatformReportCatalog() {
  return useQuery({ queryKey: ["platform-report-catalog"], retry: false,
    queryFn: () => staffRequest<ReportCatalog>("/admin/reports/catalog") });
}
export function useAnalyticsMakerspaces(page: number, reportKey: string) {
  return useQuery({ queryKey: ["platform-analytics-makerspaces", page, reportKey], retry: false,
    queryFn: () => staffRequest<AnalyticsMakerspacePage>(`/admin/platform/analytics/makerspaces?${new URLSearchParams({ page: String(page), report_key: reportKey })}`) });
}

// Fallbacks mirror the registry for cached responses from servers predating chart metadata.
export const PLATFORM_CHART_SPECS: Record<"platform-services" | "platform-usage", ReportChartSpec> = {
  "platform-services": {
    series: ["makerspace", "service", "purpose", "provider_source", "status", "bucket"], x: { field: "day", kind: "time" },
    values: [{ field: "count", unit: "operations" }, { field: "amount", unit: "currency" }],
    currency_field: "currency", partition: "currency", negatives: "clip", truncation: null, alt_template: "{count} operations",
  },
  "platform-usage": {
    series: ["makerspace", "metric", "entity_kind", "entity_id"], x: { field: "period", kind: "time" },
    values: [{ field: "value", unit: "unit" }], currency_field: "currency", partition: "unit",
    negatives: "clip", truncation: null, alt_template: "{value} {unit} for {metric}",
  },
};
