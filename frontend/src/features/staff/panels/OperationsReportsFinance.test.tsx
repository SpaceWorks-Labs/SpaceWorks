import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { reportItem } from "../../../test/analyticsFixtures";
import { OperationsReportsFinance } from "./OperationsReportsFinance";
import type { ReportCatalogItem } from "./operationsReportsConfig";

const { useStaffGet } = vi.hoisted(() => ({ useStaffGet: vi.fn() }));
vi.mock("./shared", async () => ({ ...await vi.importActual<typeof import("./shared")>("./shared"), useStaffGet }));

const report: ReportCatalogItem = reportItem("revenue-over-time", {
  title: "Revenue", fields: [], exportable: true, summary: false,
  required_modules: [], available: true, unavailable_reason: null, grains: ["day", "week", "month"],
  chart_hint: "line", chart_spec: null, aggregate_supported: false,
});

describe("Finance report charts", () => {
  it("keeps currencies separate while summing subjects inside each local period", () => {
    useStaffGet.mockReturnValue({ isLoading: false, error: null, data: { rows: [], typed_rows: [
      { period: "2026-10-11", currency: "usd", subject_type: "booking", collected_amount: "10.00", owed_amount: "2.00", refunded_amount: "1.00" },
      { period: "2026-10-11", currency: "usd", subject_type: "loan_deposit", collected_amount: "5.00", owed_amount: "1.00", refunded_amount: "1.00" },
      { period: "2026-10-11", currency: "inr", subject_type: "booking", collected_amount: "500.00", owed_amount: "20.00", refunded_amount: "10.00" },
    ] } });
    render(<OperationsReportsFinance catalog={[report]} analyticsBase="/admin/makerspace/7/analytics" scopeKey={7}
      startDate="" endDate="" grain="week" aggregate={false} makerspaceName={id => String(id)} />);
    for (const [label, total] of [["Collected USD", "15"], ["Collected INR", "500"], ["Owed USD", "3"]]) {
      const chart = within(screen.getByRole("figure", { name: `Line chart of ${label}` }));
      expect(chart.getByRole("img", { name: `Line chart of ${label}; exact values in the table.` })).toBeVisible();
      fireEvent.click(chart.getByRole("button", { name: "Show as table" }));
      const row = chart.getByRole("cell", { name: "2026-10-11" }).closest("tr")!;
      expect(within(row).getByRole("cell", { name: total })).toBeVisible();
    }
    expect(useStaffGet.mock.calls[0][1]).toContain("grain=week");
  });
});
