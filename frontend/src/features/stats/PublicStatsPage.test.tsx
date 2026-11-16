import type { ReactElement } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TenantProvider } from "../../lib/tenant";
import type { PublicStatsResponse } from "./api";

const mocks = vi.hoisted(() => ({ apiGet: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"),
  apiGet: mocks.apiGet }));
vi.mock("../inventory/usePublicInventory", () => ({ useTenantBootstrap: () => ({ data: undefined }) }));

import { PublicStatsPage } from "./PublicStatsPage";
import { PublicStatsTvPage } from "./PublicStatsTvPage";

const count = (value: number | null) => ({ value, suppressed: value === null });
export function statsFixture(overrides: Partial<PublicStatsResponse> = {}): PublicStatsResponse {
  return {
    sections: ["community", "events", "machines"],
    period: { key: "month", label: "November 2026", start: "2026-11-01T00:00:00Z", end: "2026-12-01T00:00:00Z" },
    headline: [{ key: "community.bookings", section: "community", label: "Bookings", kind: "count", ...count(null) },
      { key: "machines.hours", section: "machines", label: "Machine hours", kind: "hours", value: 12.5, suppressed: false }],
    metrics: [
      { key: "community.bookings", section: "community", label: "Bookings", kind: "count", ...count(null) },
      { key: "community.active_members", section: "community", label: "Active members", kind: "count", ...count(42) },
      { key: "events.held", section: "events", label: "Events held", kind: "count", ...count(5) },
      { key: "machines.hours", section: "machines", label: "Machine hours", kind: "hours", value: 12.5, suppressed: false },
    ],
    tv: { enabled: true, refresh_seconds: 45 },
    machines: { usage_hours: 120 }, printing: null, hardware: null, current_loans: null,
    events: { upcoming: [{ public_token: "tok-1", title: "Solder night", starts_at: "2026-11-20T18:00:00Z",
      ends_at: "2026-11-20T20:00:00Z", image_url: null }], upcoming_count: count(null), held: count(5), attendees: count(31) },
    community: { active_members: count(42), new_members: count(null), bookings: count(null), checkins: null },
    ...overrides,
  };
}

function show(path: string, element: ReactElement, routePath: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><TenantProvider><Routes>
    <Route path={routePath} element={element} />
  </Routes></TenantProvider></MemoryRouter></QueryClientProvider>);
}

beforeEach(() => { mocks.apiGet.mockReset(); mocks.apiGet.mockResolvedValue(statsFixture()); });

describe("public stats page (#170)", () => {
  it("removes hidden headlines, event lists and null counts without showing zeroes", async () => {
    const data = statsFixture();
    data.visibility = { "community.bookings": false, "machines.hours": false, "events.upcoming_list": false, "events.held": false };
    data.events!.held = null;
    data.events!.upcoming_count = null;
    data.events!.attendees = null;
    data.machines = null;
    data.sections = ["events", "community"];
    mocks.apiGet.mockResolvedValue(data);
    show("/m/lab/stats", <PublicStatsPage />, "/m/:slug/stats");
    await screen.findByRole("heading", { name: "Community" });
    expect(screen.queryByText("12.5 h")).toBeNull();
    expect(screen.queryByRole("link", { name: /Solder night/ })).toBeNull();
    expect(screen.queryByText("Events held, November 2026")).toBeNull();
    expect(screen.queryByRole("region", { name: "Headline numbers" })).toBeNull();
    expect(screen.queryByText("0")).toBeNull();
  });
  it("renders the configured sections in order with the headline first", async () => {
    show("/m/lab/stats", <PublicStatsPage />, "/m/:slug/stats");
    expect(await screen.findByRole("heading", { name: "Community" })).toBeVisible();
    const headings = screen.getAllByRole("heading", { level: 2 }).map(node => node.textContent);
    expect(headings.filter(text => ["Community", "Events", "Machines"].includes(text ?? ""))).toEqual(["Community", "Events", "Machines"]);
    const headline = screen.getByRole("region", { name: "Headline numbers" });
    expect(within(headline).getByText("12.5 h")).toBeVisible();
    expect(mocks.apiGet).toHaveBeenCalledWith("/public/lab/stats/");
  });

  it("never shows a suppressed count as a number", async () => {
    show("/m/lab/stats", <PublicStatsPage />, "/m/:slug/stats");
    await screen.findByRole("heading", { name: "Community" });
    expect(screen.getAllByText("Fewer than 3").length).toBeGreaterThanOrEqual(3);
    expect(screen.getByText("42")).toBeVisible();
    expect(screen.queryByText("Check-ins, November 2026")).toBeNull();
  });

  it("links upcoming events and offers TV mode only while it is on", async () => {
    const view = show("/m/lab/stats", <PublicStatsPage />, "/m/:slug/stats");
    expect(await screen.findByRole("link", { name: /Solder night/ })).toHaveAttribute("href", "/m/lab/events/tok-1");
    expect(screen.getByRole("link", { name: "Open TV mode" })).toHaveAttribute("href", "/m/lab/stats/tv");
    view.unmount();
    mocks.apiGet.mockResolvedValue(statsFixture({ tv: { enabled: false, refresh_seconds: 60 } }));
    show("/m/lab/stats", <PublicStatsPage />, "/m/:slug/stats");
    await screen.findByRole("heading", { name: "Community" });
    expect(screen.queryByRole("link", { name: "Open TV mode" })).toBeNull();
  });
});

describe("TV mode route (#170)", () => {
  it("uses the same hidden metric and upcoming-list choices on the TV board", async () => {
    mocks.apiGet.mockResolvedValue(statsFixture({ visibility: { "machines.hours": false, "events.upcoming_list": false } }));
    show("/m/lab/stats/tv", <PublicStatsTvPage />, "/m/:slug/stats/tv");
    await screen.findByRole("heading", { name: "Community" });
    expect(screen.queryByText("12.5 h")).toBeNull();
    expect(screen.queryByText("Solder night")).toBeNull();
    expect(screen.getAllByText("Fewer than 3").length).toBeGreaterThan(0);
  });
  it("renders a full-screen board without public navigation", async () => {
    show("/m/lab/stats/tv", <PublicStatsTvPage />, "/m/:slug/stats/tv");
    expect(await screen.findByRole("region", { name: "Headline numbers" })).toBeVisible();
    expect(screen.getByRole("heading", { level: 2, name: "Community" })).toBeVisible();
    expect(screen.getByText("Solder night")).toBeVisible();
    expect(screen.queryByRole("navigation")).toBeNull();
    expect(screen.queryByRole("link", { name: "Browse catalogue" })).toBeNull();
  });

  it("explains when the Space Manager has TV mode off", async () => {
    mocks.apiGet.mockResolvedValue(statsFixture({ tv: { enabled: false, refresh_seconds: 60 } }));
    show("/m/lab/stats/tv", <PublicStatsTvPage />, "/m/:slug/stats/tv");
    expect(await screen.findByText(/TV mode is off for this makerspace/)).toBeVisible();
  });

  it("titles the stats page and the TV board with the makerspace name", async () => {
    const first = show("/m/lab/stats", <PublicStatsPage />, "/m/:slug/stats");
    await screen.findByRole("heading", { name: "Community" });
    expect(document.title).toBe("Lab in numbers");
    first.unmount();
    show("/m/lab/stats/tv", <PublicStatsTvPage />, "/m/:slug/stats/tv");
    await screen.findByRole("heading", { name: "Community" });
    expect(document.title).toBe("Lab in numbers");
    expect(document.head.querySelector('meta[name="robots"]')).toHaveAttribute("content", expect.stringContaining("noindex"));
  });
});
