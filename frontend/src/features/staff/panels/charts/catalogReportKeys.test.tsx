import { afterEach, expect, it, vi } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import { ReportChartResult } from "../ReportAreaSections";
import { reportChartCases } from "../../../../test/reportChartCases";
import { mockAnalyticsFetch, renderAnalytics, reportItem } from "../../../../test/analyticsFixtures";
import type { ChartRecord } from "./chartSpec";
import { funnelInput, wireChartSpec } from "./wireChartSpec";
import { toChartData } from "./chartSpec";
import { rankedTimeSeries } from "./rankedTimeSeries";
import { CatalogChartPanel } from "./CatalogChartPanel";
import { chartSpec } from "../../../../test/analyticsFixtures";

afterEach(() => vi.unstubAllGlobals());
it("renders detail table specs without charting identifiers or inventing counts", () => {
  renderAnalytics(<CatalogChartPanel title="Reservations" hint="table" spec={chartSpec("booking_id", [])}
    rows={[{ booking_id: 101, status: "confirmed" }, { booking_id: 203, status: "completed" }]} />);
  expect(screen.getByRole("table")).toHaveTextContent("101");
  expect(screen.getByRole("table")).toHaveTextContent("203");
  expect(screen.queryByRole("figure")).not.toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(screen.queryByRole("columnheader", { name: "count" })).not.toBeInTheDocument();
});

it.each(reportChartCases)("renders the $key serializer/chart contract", async ({ key, hint, spec, grains }) => {
  const row: Record<string, unknown> = { makerspace_id: 11, measurement_unit: "grams", unit: "hours", currency: "USD" };
  if (spec) {
    for (const field of spec.series) row[field] ??= "Example";
    row[spec.x.field] = spec.x.kind === "time" ? "2026-10-01" : "Example category";
    for (const value of spec.values) row[value.field] = 2.5;
  } else row.count = 2.5;
  mockAnalyticsFetch(() => ({ rows: [], typed_rows: [row] }));
  renderAnalytics(<ReportChartResult report={reportItem(key, { chart_hint: hint, chart_spec: spec, grains })}
    base="/admin/makerspace/11/analytics" makerspaceId={11} period={{ start: "", end: "", grain: "day" }} />);
  fireEvent.click(await screen.findByRole("button", { name: "Show report data" }));
  expect(screen.getByRole("table", { name: /full report data/ })).toHaveTextContent("2.5");
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  if (spec) expect(screen.getAllByRole("figure").length).toBeGreaterThan(0);
});

it("preserves negative values and separates currencies, measurement units and tenants", () => {
  const spec = { series: ["material"], x: { field: "period", kind: "time" as const },
    values: [{ field: "quantity", unit: "measurement_unit" }, { field: "cost", unit: "minor currency units" }],
    currency_field: "currency", partition: "tenant" as const, negatives: "allow" as const, truncation: { top_n: 5, other_label: "Other" }, alt_template: "{count} observations" };
  const rows: ChartRecord[] = [
    { makerspace_id: 11, period: "2026-10-01", material: "PLA", measurement_unit: "grams", currency: "USD", quantity: -5, cost: -10 },
    { makerspace_id: 12, period: "2026-10-01", material: "PLA", measurement_unit: "ml", currency: "INR", quantity: 7, cost: 20 },
  ];
  const data = toChartData(wireChartSpec(spec, "multi_line", rows), rows);
  expect(new Set(data.series.map(series => series.panelKey)).size).toBe(4);
  expect(data.series.some(series => series.unit === "grams" && series.points[0].value === -5)).toBe(true);
  expect(data.series.some(series => series.unit === "ml" && series.currency === "INR")).toBe(true);
  expect(data.series.every(series => typeof series.points[0].x === "number")).toBe(true);
});

it("pivots column-based funnels into ordered stages while preserving event provenance", () => {
  const spec = wireChartSpec({ series: ["event_id"], x: { field: "period", kind: "category" },
    values: [{ field: "registered", unit: "people" }, { field: "attended", unit: "people" }],
    currency_field: null, partition: null, negatives: "clip", truncation: null, alt_template: "{count} observations" }, "funnel");
  const input = funnelInput(spec, [{ event_id: 1, period: "October", registered: 5, attended: 3 }]);
  const data = toChartData(input.spec, input.rows);
  expect(data.series).toHaveLength(1);
  expect(data.series[0].label).toContain("October");
  expect(data.series[0].points.map(point => [point.label, point.value])).toEqual([["registered", 5], ["attended", 3]]);
});

it("ranks time series within each measure and tenant, preserving dates and Other values", () => {
  const spec = reportChartCases.find(entry => entry.key === "machine-usage")!.spec!;
  const input = { ...spec, truncation: { top_n: 1, other_label: "Other" } };
  const rows = [
    { makerspace_id: 11, period: "2026-10-01", machine_name: "Laser", measure: "service", service_hours: 8 },
    { makerspace_id: 11, period: "2026-10-01", machine_name: "Mill", measure: "service", service_hours: 3 },
    { makerspace_id: 11, period: "2026-10-02", machine_name: "Mill", measure: "service", service_hours: 2 },
    { makerspace_id: 11, period: "2026-10-01", machine_name: "Laser", measure: "manual", manual_hours: 100 },
  ];
  const data = rankedTimeSeries(input, toChartData(wireChartSpec(input), rows));
  const service = data.series.filter(series => series.valueField === "service_hours");
  expect(service).toHaveLength(2);
  expect(service.find(series => series.dimensions?.includes("Other"))?.points.map(point => point.value)).toEqual([3, 2]);
  expect(data.series.find(series => series.valueField === "manual_hours")?.points[0].value).toBe(100);
  expect(data.series.every(series => series.points.every(point => typeof point.x === "number"))).toBe(true);
});
