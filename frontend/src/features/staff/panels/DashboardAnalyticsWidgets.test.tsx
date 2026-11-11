import { act, cleanup, fireEvent, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { chartSpec, errorResponse, mockAnalyticsFetch, renderAnalytics, reportData } from "../../../test/analyticsFixtures";
import { DashboardAnalyticsWidgets } from "./DashboardAnalyticsWidgets";
import type { AnalyticsReport, DashboardWidget } from "./analyticsApi";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

function widget(key: string): DashboardWidget {
  return { key, title: key, required_action: "view_inventory", required_modules: ["reports"], kind: "trend",
    report_keys: [key], default_period: 30, chart_spec: chartSpec(),
    data: { typed_rows: [], meta: { deferred: true, start: "2026-09-18", end: "2026-10-17" } } };
}

it("loads widgets independently and retries a failed report without blocking counters or other charts", async () => {
  let finishSlow!: (value: AnalyticsReport) => void;
  const slow = new Promise<AnalyticsReport>(resolve => { finishSlow = resolve; });
  let attempts = 0;
  const fetcher = mockAnalyticsFetch(url => {
    expect(url.pathname).toContain("/admin/makerspace/11/analytics/");
    expect(url.searchParams.get("start")).toBe("2026-09-18");
    expect(url.searchParams.get("end")).toBe("2026-10-17");
    if (url.pathname.endsWith("/consumable-usage")) return slow;
    if (url.pathname.endsWith("/loan-throughput") && attempts++ === 0) return errorResponse(503);
    return reportData();
  });
  renderAnalytics(<><p>Pending requests: 3</p><DashboardAnalyticsWidgets makerspaceId={11} reportsHref="/reports"
    widgets={[widget("consumable-usage"), widget("loan-throughput"), widget("stock-health")]} /></>);
  expect(screen.getByText("Pending requests: 3")).toBeInTheDocument();
  const failed = within(screen.getByRole("region", { name: "loan-throughput" }));
  expect(await failed.findByRole("alert")).toBeInTheDocument();
  const ready = within(screen.getByRole("region", { name: "stock-health" }));
  expect(await ready.findByRole("button", { name: "Show report data" })).toBeInTheDocument();
  expect(fetcher).toHaveBeenCalledTimes(3);
  fireEvent.click(failed.getByRole("button", { name: "Retry" }));
  expect(await failed.findByRole("button", { name: "Show report data" })).toBeInTheDocument();
  expect(attempts).toBe(2);
  await act(async () => { finishSlow(reportData()); });
  expect(await within(screen.getByRole("region", { name: "consumable-usage" }))
    .findByRole("button", { name: "Show report data" })).toBeInTheDocument();
});

it("draws collected and net as separate lines instead of a double-counted stack", () => {
  const revenue = widget("revenue-over-time");
  revenue.chart_spec = chartSpec("period", ["collected_amount", "refunded_amount", "net_amount"], {
    values: ["collected_amount", "refunded_amount", "net_amount"].map(field => ({ field, unit: "currency_major" })),
    currency_field: "currency", partition: "currency", negatives: "allow",
  });
  revenue.data = { typed_rows: [{ period: "2026-10-17", currency: "USD", collected_amount: 100,
    refunded_amount: 0, net_amount: 100 }] };
  renderAnalytics(<DashboardAnalyticsWidgets widgets={[revenue]} makerspaceId={11} reportsHref="/reports" />);
  const chart = screen.getByRole("img");
  expect(chart).toHaveAccessibleName(/time on horizontal axis/);
  expect(chart.querySelectorAll("polyline")).toHaveLength(3);
  expect(within(chart).getByText("100")).toBeInTheDocument();
  expect(within(chart).queryByText("200")).not.toBeInTheDocument();
});

it("fetches deferred platform dashboard widgets through the platform tenant read surface", async () => {
  const fetcher = mockAnalyticsFetch(url => {
    expect(url.pathname).toBe("/api/v1/admin/platform/analytics/makerspaces/11/analytics/stock-health");
    return reportData();
  });
  renderAnalytics(<DashboardAnalyticsWidgets widgets={[widget("stock-health")]} makerspaceId={11}
    analyticsBase="/admin/platform/analytics/makerspaces/11/analytics" />);
  expect(await screen.findByRole("button", { name: "Show report data" })).toBeInTheDocument();
  expect(fetcher).toHaveBeenCalledOnce();
  expect(screen.queryByRole("link", { name: "Open in reports" })).not.toBeInTheDocument();
});
