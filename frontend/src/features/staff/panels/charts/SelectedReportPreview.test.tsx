import { render, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { SelectedReportPreview } from "../SelectedReportPreview";
import { ReportSelectionProvider, SelectedReportPanel } from "../OperationsReportSelection";
import { reportDefinitions } from "../operationsReportsConfig";
import { useStaffGet } from "../shared";
import type { ReportChartSpec } from "../analyticsApi";

vi.mock("../shared", () => ({
  useStaffGet: vi.fn(),
  Panel: ({ title, children }: { title: string; children: React.ReactNode }) => <section aria-label={title}>{children}</section>,
}));
const mockGet = vi.mocked(useStaffGet);
const report = { ...reportDefinitions[0], key: "most-lent", title: "Most lent", summary: false };
const spec: ReportChartSpec = { series: [], x: { field: "product", kind: "category" },
  values: [{ field: "count", unit: "loans" }], currency_field: null, partition: null,
  negatives: "allow", truncation: null, alt_template: "{points} products." };
const props = { report, analyticsBase: "/analytics", scopeKey: 1, start: "", end: "", grain: "day", columns: [], months: "" };

beforeEach(() => {
  mockGet.mockReturnValue({ data: { rows: [["product", "count"], ["Drill", 3]] }, isLoading: false, error: null, refetch: vi.fn() } as unknown as ReturnType<typeof useStaffGet>);
});

it("keeps the table fallback when chart_spec is absent", () => {
  render(<SelectedReportPreview {...props} />);
  expect(screen.getByRole("table")).toBeInTheDocument();
  expect(screen.getByText("Drill")).toBeInTheDocument();
  expect(screen.queryByRole("figure")).not.toBeInTheDocument();
});

it("projects header-based rows when a catalog entry supplies chart_spec", () => {
  render(<SelectedReportPreview {...props} report={{ ...report, chart_spec: spec }} />);
  expect(screen.getByRole("figure")).toBeInTheDocument();
  expect(screen.getByText("Drill")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Show as table" })).toBeInTheDocument();
});

it("prefers the catalog chart over an older specialist for the selected report", () => {
  const entry = { ...report, chart_spec: spec };
  render(<ReportSelectionProvider selected={report.key} columns={[]} catalog={[entry]} hardware finance={false} machines={false}>
    <SelectedReportPanel reportKey={report.key} title="Old specialist"><p>Old specialist body</p></SelectedReportPanel>
    <SelectedReportPreview {...props} report={entry} />
  </ReportSelectionProvider>);
  expect(screen.getByRole("figure")).toBeInTheDocument();
  expect(screen.queryByText("Old specialist body")).not.toBeInTheDocument();
});

it("prefers typed rows and does not let table column selection remove chart fields", () => {
  mockGet.mockReturnValue({ data: { rows: [], typed_rows: [{ product: "Lathe", count: 4 }] }, isLoading: false, error: null, refetch: vi.fn() } as unknown as ReturnType<typeof useStaffGet>);
  render(<SelectedReportPreview {...props} columns={["product"]} report={{ ...report, chart_spec: spec }} />);
  expect(screen.getByText("Lathe")).toBeInTheDocument();
  expect(screen.queryByText(/No activity/)).not.toBeInTheDocument();
});
