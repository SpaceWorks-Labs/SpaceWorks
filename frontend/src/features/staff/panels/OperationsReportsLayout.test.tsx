import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { reportItem } from "../../../test/analyticsFixtures";
import { OperationsReports } from "./OperationsReports";
import { OperationsReportNavigation } from "./OperationsReportNavigation";
import type { Makerspace } from "./shared";
import type { ReportCatalogItem } from "./operationsReportsConfig";
import { ContentTarget } from "../../../components/layouts/LayoutFrame";

const { request, download } = vi.hoisted(() => ({ request: vi.fn(), download: vi.fn(() => Promise.resolve()) }));
vi.mock("../../../lib/api", async () => ({ ...await vi.importActual("../../../lib/api"), staffRequest: request, downloadStaffFile: download }));
const report: ReportCatalogItem = reportItem("most-lent", { title: "Most lent", available: true, exportable: true,
  summary: false, required_modules: [], fields: [], unavailable_reason: null, grains: ["day"], chart_hint: "table", chart_spec: null, aggregate_supported: true });
const space = { id: 7, name: "Lab", enabled_modules: ["reports"] } as Makerspace;
beforeEach(() => {
  request.mockReset(); download.mockClear();
  request.mockImplementation((url: string) => Promise.resolve(url.endsWith("/catalog") ? { results: [report] }
    : url.endsWith("/report-schedules") || url.endsWith("/notification-destinations") ? [] : { rows: [], typed_rows: [] }));
});
function panel() {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <main id="main-content" tabIndex={-1}><ContentTarget.Provider value={true}><OperationsReports makerspace={space} makerspaces={[space]} isSuperadmin={false} canViewAudit={false} canManageMachines={false} /></ContentTarget.Provider></main>
  </QueryClientProvider>);
}
it("exports the selected report from the page header and opens schedules in a drawer", async () => {
  panel();
  const action = await screen.findByRole("button", { name: /^Export$/ });
  await waitFor(() => expect(action).toBeEnabled());
  fireEvent.click(action);
  await waitFor(() => expect(download).toHaveBeenCalledWith("/admin/makerspace/7/reports/most-lent/export?format=csv&grain=day", "most-lent.csv"));
  const schedule = screen.getAllByRole("button", { name: /Schedule/ })[0];
  fireEvent.click(schedule);
  expect(await screen.findByRole("dialog", { name: "Scheduled reports" })).toBeVisible();
  expect(await screen.findByRole("button", { name: "New schedule" })).toBeVisible();
  expect(document.querySelectorAll("#main-content")).toHaveLength(1);
});
it("applies a seven-day range while keeping custom date fields available", async () => {
  panel();
  fireEvent.click(await screen.findByRole("radio", { name: "7 days" }));
  const start = (screen.getByLabelText("Start") as HTMLInputElement).value;
  const end = (screen.getByLabelText("End") as HTMLInputElement).value;
  expect((new Date(end).getTime() - new Date(start).getTime()) / 86400000).toBe(6);
  await waitFor(() => expect(request.mock.calls.some(([url]) => String(url).includes(`start=${start}&end=${end}`))).toBe(true));
  fireEvent.change(screen.getByLabelText("Start"), { target: { value: "2026-01-01" } });
  expect(screen.getByRole("radio", { name: "Custom" })).toHaveAttribute("aria-checked", "true");
});
it("groups the report navigation and hides reports whose module is off (#183B)", () => {
  const onSelect = vi.fn();
  render(<OperationsReportNavigation reports={[report, { ...report, key: "booking-utilization", title: "Booking utilization", available: false, unavailable_reason: "Needs Bookings module" }]} selected="summary" onSelect={onSelect} />);
  expect(screen.getByRole("heading", { name: "Inventory" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Booking utilization/ })).toBeNull();
  expect(screen.queryByText("Needs Bookings module")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Most lent" }));
  expect(onSelect).toHaveBeenCalledWith("most-lent");
});

it("leads the report with a picker below xl and keeps the grouped list for xl only", async () => {
  panel();
  const picker = await screen.findByRole("combobox", { name: "Report" });
  expect(picker.closest(".xl\\:hidden")).not.toBeNull();
  expect(picker.closest("section")).toHaveAccessibleName("Report configuration");
  expect(screen.getByRole("navigation", { name: "Reports" })).toHaveClass("hidden", "xl:block");
});

it("opens on the Summary report when the catalog lists it", async () => {
  request.mockImplementation((url: string) => Promise.resolve(url.endsWith("/catalog") ? { results: [report, { ...report, key: "summary", title: "Summary", summary: true, exportable: false }] }
    : url.endsWith("/report-schedules") || url.endsWith("/notification-destinations") ? [] : { rows: [], typed_rows: [] }));
  panel();
  await waitFor(() => expect(screen.getByRole("combobox", { name: "Report" })).toHaveValue("summary"));
});
it("shows a catalog failure inline with Retry and keeps the page rendering", async () => {
  let fail = true;
  request.mockImplementation((url: string) => url.endsWith("/catalog") ? (fail ? Promise.reject(new Error("boom")) : Promise.resolve({ results: [report] }))
    : Promise.resolve(url.endsWith("/report-schedules") || url.endsWith("/notification-destinations") ? [] : { rows: [], typed_rows: [] }));
  panel();
  expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't load reports");
  expect(screen.getByRole("heading", { name: "Reports", level: 1 })).toBeVisible();
  fail = false;
  fireEvent.click(screen.getByRole("button", { name: "Retry" }));
  await waitFor(() => expect(screen.queryByRole("button", { name: "Retry" })).toBeNull());
  expect(screen.getByRole("region", { name: "Report configuration" })).toBeInTheDocument();
});
