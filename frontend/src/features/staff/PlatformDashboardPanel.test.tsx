import { afterEach, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { PlatformDashboardPanel } from "./PlatformDashboardPanel";
import { PlatformAnalyticsPicker } from "./PlatformAnalyticsPicker";
import { errorResponse, mockAnalyticsFetch, renderAnalytics, reportItem } from "../../test/analyticsFixtures";
import { expectNoA11yViolations } from "../../test/axe";

afterEach(() => vi.unstubAllGlobals());
const picker = { count: 1, next: null, previous: null, results: [{ id: 11, name: "Workshop", slug: "workshop" }] };
const monitoring = { checked_at: "2026-10-17T10:00:00Z", tenants_by_state: { active: 1 }, usage_totals: {}, tenants: [],
  backup: { status: "ok", automatic_enabled: false, last_success_at: null }, offsite: [], scheduler: [], failed_deliveries: { email: 0, notifications: 0 } };
const period = { start: "", end: "", grain: "day" };

it("renders services and usage for every makerspace without raw identifiers", async () => {
  mockAnalyticsFetch(url => {
    if (url.pathname.endsWith("/dashboard")) return monitoring;
    if (url.pathname.endsWith("/problems")) return { checked_at: monitoring.checked_at, results: [] };
    if (url.pathname.endsWith("/makerspaces")) return picker;
    if (url.pathname.endsWith("platform-services")) return { rows: [], typed_rows: [
      { day: "2026-10-01", service: "email", bucket: "makerspace", makerspace_id: 11, provider_source: "platform", status: "sent", count: 4, currency: null, amount: null },
    ] };
    return { rows: [], typed_rows: [{ makerspace_id: 11, period: "2026-10-01", metric: "member_growth", entity_kind: "makerspace", unit: "count", value: 3 }] };
  });
  const { container } = renderAnalytics(<PlatformDashboardPanel />);
  await screen.findByRole("button", { name: "Show report data" });
  const services = screen.getByRole("region", { name: "Platform services" });
  const usage = screen.getByRole("region", { name: "Platform usage" });
  fireEvent.click(within(services).getByRole("button", { name: "Show report data" }));
  const table = within(services).getByRole("table", { name: /full report data/ });
  expect(within(table).queryByRole("columnheader", { name: "makerspace id" })).not.toBeInTheDocument();
  expect(within(table).queryByRole("columnheader", { name: /key|token|host/ })).not.toBeInTheDocument();
  expect(within(usage).queryByText("Hidden makerspaces")).not.toBeInTheDocument();
  expect(within(services).queryByText("Hidden makerspaces")).not.toBeInTheDocument();
  expect(screen.getByLabelText("Makerspace")).toBeInTheDocument();
  await expectNoA11yViolations(container);
});

it.each(["catalog", "report"])("honors a picker %s hard block with a clear 403 message", async blocked => {
  mockAnalyticsFetch(url => {
    if (url.pathname.endsWith("/makerspaces")) return picker;
    if (url.pathname.endsWith("/catalog")) return blocked === "catalog" ? errorResponse(403) : { results: [reportItem("summary")] };
    return errorResponse(403);
  });
  renderAnalytics(<PlatformAnalyticsPicker period={period} />);
  await screen.findByRole("option", { name: "Workshop" });
  fireEvent.change(screen.getByLabelText("Makerspace"), { target: { value: "11" } });
  expect(await screen.findByRole("alert")).toHaveTextContent("Access to this makerspace's analytics is blocked");
});

it("opens tenant charts through scoped endpoints and paginates the picker", async () => {
  const fetcher = mockAnalyticsFetch(url => {
    if (url.pathname.endsWith("/makerspaces")) return url.searchParams.get("page") === "2"
      ? { count: 25, next: null, previous: "?page=1", results: [{ id: 12, name: "Second workshop", slug: "second" }] }
      : { ...picker, count: 25, next: "?page=2" };
    if (url.pathname.endsWith("/catalog")) return { results: [reportItem("summary")] };
    return { typed_rows: [{ period: "2026-10-01", count: 5 }], rows: [] };
  });
  renderAnalytics(<PlatformAnalyticsPicker period={period} />);
  await screen.findByRole("option", { name: "Workshop" });
  fireEvent.change(screen.getByLabelText("Makerspace"), { target: { value: "11" } });
  await screen.findByRole("button", { name: "Show report data" });
  expect(screen.getByRole("button", { name: "Open Workshop dashboard" })).toBeInTheDocument();
  expect(fetcher.mock.calls.some(([url]) => String(url).includes("/admin/platform/analytics/makerspaces/11/reports/catalog"))).toBe(true);
  expect(fetcher.mock.calls.some(([url]) => String(url).includes("/admin/platform/analytics/makerspaces/11/analytics/summary"))).toBe(true);
  expect(fetcher.mock.calls.some(([url]) => String(url).includes("/admin/makerspace/11/"))).toBe(false);
  fireEvent.click(screen.getByRole("button", { name: /next/i }));
  await screen.findByRole("option", { name: "Second workshop" });
});

it("keeps picker dashboard and exports on platform routes", async () => {
  const fetcher = mockAnalyticsFetch(url => {
    if (url.pathname.endsWith("/makerspaces")) return picker;
    if (url.pathname.endsWith("/catalog")) return { results: [reportItem("machine-usage", { exportable: true, allowed_formats: ["csv"] })] };
    if (url.pathname.endsWith("/dashboard")) return { pending_requests: 3, widgets: [] };
    if (url.pathname.endsWith("/export")) return new Response("machine,hours\nDrill,2", { headers: { "Content-Type": "text/csv" } });
    return { typed_rows: [{ period: "2026-10-01", count: 5 }], rows: [] };
  });
  const create = vi.fn(() => "blob:fg-export");
  const revoke = vi.fn();
  vi.stubGlobal("URL", class extends URL {
    static createObjectURL = create;
    static revokeObjectURL = revoke;
  });
  const clicked = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  try {
    renderAnalytics(<PlatformAnalyticsPicker period={{ start: "2026-10-01", end: "2026-10-18", grain: "day" }} />);
    await screen.findByRole("option", { name: "Workshop" });
    fireEvent.change(screen.getByLabelText("Picker report scope"), { target: { value: "machine-usage" } });
    await screen.findByRole("option", { name: "Workshop" });
    fireEvent.change(screen.getByLabelText("Makerspace"), { target: { value: "11" } });
    fireEvent.click(await screen.findByRole("button", { name: "Open Workshop dashboard" }));
    const dashboard = await screen.findByRole("region", { name: "Workshop dashboard" });
    await waitFor(() => expect(dashboard).toHaveTextContent("Pending requests3"));
    fireEvent.click(screen.getByRole("button", { name: "Export CSV" }));
    await waitFor(() => expect(create).toHaveBeenCalledOnce());
    expect(clicked).toHaveBeenCalledOnce();
    const paths = fetcher.mock.calls.map(([url]) => new URL(String(url), "http://localhost"));
    expect(paths.some(url => url.pathname.endsWith("/admin/platform/analytics/makerspaces/11/dashboard"))).toBe(true);
    const exported = paths.find(url => url.pathname.endsWith("/reports/machine-usage/export"))!;
    expect(exported.pathname).toContain("/admin/platform/analytics/makerspaces/11/");
    expect(Object.fromEntries(exported.searchParams)).toEqual({ start: "2026-10-01", end: "2026-10-18", grain: "day", format: "csv" });
    expect(paths.some(url => url.pathname.includes("/admin/makerspace/"))).toBe(false);
    await waitFor(() => expect(revoke).toHaveBeenCalledWith("blob:fg-export"), { timeout: 2000 });
  } finally { clicked.mockRestore(); }
});

it("shows independent service failures and empty usage", async () => {
  mockAnalyticsFetch(url => {
    if (url.pathname.endsWith("/dashboard")) return monitoring;
    if (url.pathname.endsWith("/problems")) return { checked_at: monitoring.checked_at, results: [] };
    if (url.pathname.endsWith("platform-services")) return errorResponse(503);
    if (url.pathname.endsWith("/makerspaces")) return { ...picker, results: [] };
    return { typed_rows: [], rows: [] };
  });
  renderAnalytics(<PlatformDashboardPanel />);
  await waitFor(() => expect(within(screen.getByRole("region", { name: "Platform services" })).getByRole("alert")).toBeInTheDocument());
  expect(within(screen.getByRole("region", { name: "Platform usage" })).getByText(/No activity in this period/)).toBeInTheDocument();
});
