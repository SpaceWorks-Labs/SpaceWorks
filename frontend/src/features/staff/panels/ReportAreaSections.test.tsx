import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { useState } from "react";
import { OperationsReports } from "./OperationsReports";
import { ReportAreaSections, ReportChartResult } from "./ReportAreaSections";
import { REPORT_AREAS } from "./reportAreas";
import { chartSpec, errorResponse, mockAnalyticsFetch, renderAnalytics, reportData, reportItem, space } from "../../../test/analyticsFixtures";
import { expectNoA11yViolations } from "../../../test/axe";

afterEach(() => { vi.unstubAllGlobals(); });
const period = { start: "2026-10-01", end: "2026-10-17", grain: "week" };
const entries = ["loan-throughput", "stock-health", "machine-usage", "booking-occupancy", "event-funnel", "membership-growth", "payments-ageing", "communications-health", "audit-activity", "roster-export", "incidents-register", "donations-pledges"].map(key => reportItem(key));

describe("reports area sections", () => {
  it("lists only catalog keys in every area and fetches only the expanded report", async () => {
    const fetcher = mockAnalyticsFetch(() => reportData());
    function Reports() {
      const [selected, setSelected] = useState("loan-throughput");
      return <ReportAreaSections reports={entries} selected={selected} onSelect={setSelected} base="/admin/makerspace/11/analytics" period={period} />;
    }
    const { container } = renderAnalytics(<Reports />);
    for (const area of REPORT_AREAS) expect(screen.getByRole("region", { name: area })).toBeInTheDocument();
    expect(screen.queryByText("top-borrowers")).not.toBeInTheDocument();
    await screen.findByRole("button", { name: "Show report data" });
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(String(fetcher.mock.calls[0][0])).toContain("grain=week");
    fireEvent.click(screen.getByRole("button", { name: "Show report data" }));
    expect(screen.getByRole("table", { name: /full report data/ })).toHaveTextContent("7");
    fireEvent.click(screen.getByRole("button", { name: "stock health" }));
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
    const loans = screen.getByRole("region", { name: "Inventory" });
    expect(within(loans).queryByRole("button", { name: "Hide report data" })).not.toBeInTheDocument();
    await expectNoA11yViolations(container);
  });

  it("uses the fetched catalog and declares only supported grain choices on the Reports page", async () => {
    mockAnalyticsFetch(url => url.pathname.endsWith("catalog") ? { results: [reportItem("booking-occupancy", { grains: ["day", "month"] })] } : reportData());
    renderAnalytics(<OperationsReports makerspace={space} makerspaces={[space]} isSuperadmin={false} canViewAudit={false} canManageMachines={false} />);
    await screen.findByRole("region", { name: "Bookings" });
    const grain = screen.getByLabelText("Grain");
    expect(within(grain).queryByRole("option", { name: "week" })).not.toBeInTheDocument();
    fireEvent.change(grain, { target: { value: "month" } });
    await screen.findByRole("button", { name: "Show report data" });
  });

  it("shows identity-bearing reports only if the catalog provides them", async () => {
    const fetcher = mockAnalyticsFetch(() => reportData());
    renderAnalytics(<ReportAreaSections reports={[reportItem("top-borrowers", { identity_bearing: true })]} selected="top-borrowers"
      onSelect={() => {}} base="/analytics" period={period} />);
    expect(screen.getByText("Contains personal data")).toBeInTheDocument();
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));
  });

  it("keeps the full authorized catalog available to machine-only actors", async () => {
    mockAnalyticsFetch(url => url.pathname.endsWith("catalog") ? { results: [reportItem("machine-downtime")] } : reportData());
    renderAnalytics(<OperationsReports makerspace={space} makerspaces={[space]} isSuperadmin={false} printingOnly canViewAudit={false} canManageMachines />);
    expect(await screen.findByRole("region", { name: "Machines & service" })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Show report data" })).toBeInTheDocument();
  });

  it.each([403, 500])("shows an error for report status %s", async status => {
    mockAnalyticsFetch(() => errorResponse(status));
    renderAnalytics(<ReportChartResult report={entries[0]} base="/analytics" period={period} />);
    expect(await screen.findByRole("alert")).toHaveTextContent(status === 403 ? "blocked" : "Couldn't load");
  });

  it("does not fetch unavailable or export-only catalog entries", () => {
    const fetcher = mockAnalyticsFetch(() => reportData());
    renderAnalytics(<ReportChartResult report={reportItem("bookings", { previewable: false })} base="/analytics" period={period} />);
    expect(screen.getByText(/exports only/)).toBeInTheDocument();
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("keeps rows with a null axis in the complete report table", async () => {
    mockAnalyticsFetch(() => ({ typed_rows: [{ period: null, count: 9 }], rows: [] }));
    renderAnalytics(<ReportChartResult report={reportItem("stock-health", { chart_spec: chartSpec() })} base="/analytics" period={period} />);
    fireEvent.click(await screen.findByRole("button", { name: "Show report data" }));
    expect(screen.getByRole("table")).toHaveTextContent("9");
  });
});
