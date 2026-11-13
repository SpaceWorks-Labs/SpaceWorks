import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { chartSpec, reportItem } from "../../../test/analyticsFixtures";
import { MembershipInsightsReports } from "./MembershipInsightsReports";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api");
  return { ...actual, staffRequest };
});

function wrap(node: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}>{node}</QueryClientProvider>);
}

const year = { financial_year_start_month: 4, current_label: "2026-27", current_start: "2026-04-01", current_end: "2027-03-31",
  presets: [{ key: "this", label: "FY 2026-27", start: "2026-04-01", end: "2027-03-31" }] };
const revenue = reportItem("membership-revenue-by-plan", { title: "Collected membership revenue by plan", grains: ["month"],
  chart_spec: chartSpec("period", ["net"]) });
const forecast = reportItem("membership-renewal-forecast", { title: "Renewal forecast", grains: ["day"],
  chart_spec: chartSpec("horizon_days", ["expected_amount"]) });

function respond(results: unknown[], rows: Record<string, unknown>[] = []) {
  staffRequest.mockImplementation((path: string) => {
    if (path.endsWith("/reports/catalog")) return Promise.resolve({ results });
    if (path.endsWith("/financial-year")) return Promise.resolve(year);
    if (path.includes("/analytics/")) return Promise.resolve({ typed_rows: rows, rows: [] });
    return Promise.reject(new Error(`unexpected ${path}`));
  });
}

beforeEach(() => { staffRequest.mockReset(); });

describe("MembershipInsightsReports", () => {
  it("renders nothing when no membership report is offered (switch off or no access)", async () => {
    respond([reportItem("summary")]);
    const { container } = wrap(<MembershipInsightsReports makerspaceId={3} />);
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/3/reports/catalog"));
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });

  it("shows the report empty state when a period has no rows", async () => {
    respond([revenue, forecast]);
    wrap(<MembershipInsightsReports makerspaceId={3} />);
    expect(await screen.findByText("No activity in this period. Try a longer range.")).toBeInTheDocument();
    expect(screen.getByText(/less refunds that went back/)).toBeInTheDocument();
  });

  it("offers the unit and level leagues only when the catalogue does (membership.units on)", async () => {
    const unitLeague = reportItem("membership-unit-league", { grains: ["day"], chart_spec: chartSpec("unit_code", ["members"]) });
    const levelLeague = reportItem("membership-level-league", { grains: ["day"], chart_spec: chartSpec("level_name", ["members"]) });
    respond([revenue, unitLeague, levelLeague], [{ unit_id: 1, unit_code: "KOC", unit_name: "Kochi", level: 1, level_name: "Chapter",
      parent_code: "", members: 12, direct_members: 9, joined: 2, pending_requests: 1 }]);
    wrap(<MembershipInsightsReports makerspaceId={3} />);
    fireEvent.click(await screen.findByRole("radio", { name: "Unit league" }));
    await waitFor(() => expect(staffRequest.mock.calls.some(([path]) => String(path).includes("/analytics/membership-unit-league?"))).toBe(true));
    expect(screen.getByText(/never names/)).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Level league" })).toBeInTheDocument();
  });

  it("hides both leagues when the units switch keeps them out of the catalogue", async () => {
    respond([revenue, forecast]);
    wrap(<MembershipInsightsReports makerspaceId={3} />);
    await screen.findByRole("radio", { name: "Renewal forecast" });
    expect(screen.queryByRole("radio", { name: "Unit league" })).not.toBeInTheDocument();
    expect(screen.queryByRole("radio", { name: "Level league" })).not.toBeInTheDocument();
  });

  it("switches tabs and asks the forecast for no date range", async () => {
    respond([revenue, forecast], [{ horizon_days: 30, currency: "inr", terms_ending: 2, expected_amount: "2000.00" }]);
    wrap(<MembershipInsightsReports makerspaceId={3} />);
    fireEvent.click(await screen.findByRole("radio", { name: "Renewal forecast" }));
    await waitFor(() => expect(staffRequest.mock.calls.some(([path]) => String(path).includes("/analytics/membership-renewal-forecast"))).toBe(true));
    const call = staffRequest.mock.calls.find(([path]) => String(path).includes("/analytics/membership-renewal-forecast"))!;
    expect(String(call[0])).not.toContain("start=");
    expect(screen.queryByLabelText("Financial year")).not.toBeInTheDocument();
  });
});
