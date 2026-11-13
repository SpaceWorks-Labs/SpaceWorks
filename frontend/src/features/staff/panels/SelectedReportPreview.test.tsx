import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import { SelectedReportPreview } from "./SelectedReportPreview";
import type { ReportCatalogItem } from "./operationsReportsConfig";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../../lib/api", () => ({ staffRequest: request }));

it("uses the monthly report grain and displays only saved columns", async () => {
  request.mockResolvedValue({ rows: [["currency", "mrr", "arr"], ["usd", "20.00", "240.00"]],
    meta: { definition: "Monthly recurring plan projection" } });
  const report = { key: "membership-revenue", title: "MRR", grains: ["month"], available: true } as ReportCatalogItem;
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <SelectedReportPreview report={report} analyticsBase="/admin/makerspace/7/analytics" scopeKey={7}
      start="2026-01-01" end="" grain="day" columns={["currency", "mrr"]} months="" />
  </QueryClientProvider>);
  // 0.12.0: column headings go through reportFieldLabel (unknown keys are humanised).
  expect(await screen.findByRole("columnheader", { name: "Mrr" })).toBeVisible();
  expect(screen.queryByRole("columnheader", { name: "Arr" })).not.toBeInTheDocument();
  expect(request).toHaveBeenCalledWith("/admin/makerspace/7/analytics/membership-revenue?grain=month&start=2026-01-01");
  expect(screen.getByText("Monthly recurring plan projection")).toBeVisible();
});


it("hides cached channel data while the report is unavailable and restores it on re-enable", async () => {
  request.mockResolvedValue({ typed_rows: [
    { period: "2026-11-01", measure: "session_days", channel: "web", area: "all", value: 2 },
  ] });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const report = { key: "channel-usage", title: "Web and app use", available: true, grains: ["day"] } as ReportCatalogItem;
  const props = { report, analyticsBase: "/analytics", scopeKey: 7, start: "", end: "", grain: "day", columns: [], months: "" };
  const draw = (available: boolean) => <QueryClientProvider client={client}>
    <SelectedReportPreview {...props} report={{ ...report, available }} />
  </QueryClientProvider>;
  const view = render(draw(true));
  expect(await screen.findByText("2 active session-days")).toBeVisible();
  view.rerender(draw(false));
  expect(screen.queryByText("2 active session-days")).toBeNull();
  view.rerender(draw(true));
  expect(await screen.findByText("2 active session-days")).toBeVisible();
});
