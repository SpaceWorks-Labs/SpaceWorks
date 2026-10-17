import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import { render } from "@testing-library/react";
import type { ReportCatalogItem } from "../features/staff/panels/operationsReportsConfig";
import type { ReportChartSpec, AnalyticsReport } from "../features/staff/panels/analyticsApi";
import type { Makerspace } from "../features/staff/panels/shared";

export const chartSpec = (x = "period", values = ["count"], options: Partial<ReportChartSpec> = {}): ReportChartSpec => ({
  series: [], x: { field: x, kind: x === "period" || x === "day" ? "time" : "category" },
  values: values.map(field => ({ field, unit: "count" })), currency_field: null, partition: null,
  negatives: "clip", truncation: null, alt_template: "{count} observations", ...options,
});
export const reportItem = (key: string, options: Partial<ReportCatalogItem> = {}): ReportCatalogItem => ({
  key, title: key.replace(/-/g, " "), fields: ["period", "count"], exportable: false, summary: false,
  required_modules: [], available: true, unavailable_reason: null, grains: ["day", "week", "month"],
  chart_hint: "line", aggregate_supported: true, chart_spec: chartSpec(), ...options,
});
export const reportData = (rows = [{ period: "2026-10-01", count: 7 }]): AnalyticsReport => ({ typed_rows: rows, rows: [] });
export const space = {
  id: 11, name: "Workshop", slug: "workshop",
  enabled_modules: ["reports", "public_inventory", "request_workflow", "machines", "bookings", "events", "membership", "notifications", "devices"],
} as Makerspace;
export function renderAnalytics(element: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false } } });
  return { ...render(<QueryClientProvider client={client}><MemoryRouter>{element}</MemoryRouter></QueryClientProvider>), client };
}
export function mockAnalyticsFetch(responder: (url: URL) => unknown | Response | Promise<unknown | Response>) {
  const fetcher = vi.fn(async (input: RequestInfo | URL) => {
    const value = await responder(new URL(String(input), "http://localhost"));
    return value instanceof Response ? value : new Response(JSON.stringify(value), { status: 200, headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", fetcher);
  return fetcher;
}
export const errorResponse = (status: number) => new Response(JSON.stringify({ detail: "Access denied" }), { status });
