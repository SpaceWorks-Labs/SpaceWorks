import { useQuery } from "@tanstack/react-query";
import { staffRequest } from "../../lib/api";
import { periodParams, type AnalyticsPeriod, type AnalyticsReport, type ReportChartSpec } from "./panels/analyticsApi";

export type AnalyticsMakerspace = { id: number; name: string; slug: string };
export type AnalyticsMakerspacePage = { count: number; next: string | null; previous: string | null; results: AnalyticsMakerspace[] };
export type PlatformAnalyticsReport = AnalyticsReport & { chart_spec?: ReportChartSpec; chart_hint?: string };
export function usePlatformAnalytics(key: "platform-services" | "platform-usage", period: AnalyticsPeriod) {
  return useQuery({ queryKey: ["platform-analytics", key, period], retry: false,
    queryFn: () => staffRequest<PlatformAnalyticsReport>(`/admin/platform/analytics/${key}?${periodParams(period)}`) });
}
export function useAnalyticsMakerspaces(page: number, reportKey: string) {
  return useQuery({ queryKey: ["platform-analytics-makerspaces", page, reportKey], retry: false,
    queryFn: () => staffRequest<AnalyticsMakerspacePage>(`/admin/platform/analytics/makerspaces?${new URLSearchParams({ page: String(page), report_key: reportKey })}`) });
}

// PlatformAnalyticsView returns report rows without the registry's chart_spec.
// These mirror report_definitions_j.py until it includes that metadata in the response.
export const PLATFORM_CHART_SPECS: Record<"platform-services" | "platform-usage", ReportChartSpec> = {
  "platform-services": {
    series: ["makerspace", "service", "provider_source", "status", "bucket"], x: { field: "day", kind: "time" },
    values: [{ field: "count", unit: "operations" }, { field: "amount", unit: "currency" }],
    currency_field: "currency", partition: "currency", negatives: "clip", truncation: null, alt_template: "{count} operations",
  },
  "platform-usage": {
    series: ["makerspace", "metric", "entity_kind", "entity_id"], x: { field: "period", kind: "time" },
    values: [{ field: "value", unit: "unit" }], currency_field: "currency", partition: "unit",
    negatives: "clip", truncation: null, alt_template: "{value} {unit} for {metric}",
  },
};
