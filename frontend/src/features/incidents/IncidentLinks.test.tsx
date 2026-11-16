import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AllowedTabsContext } from "../staff/areaOverview/allowedTabsContext";
import type { Incident } from "./api";
import { IncidentRegister } from "./IncidentRegister";

const api = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", async original => ({ ...(await original<object>()), staffRequest: api.staffRequest }));

const incident = (overrides: Partial<Incident> = {}): Incident => ({
  id: 7, makerspace: 4, kind: "incident", severity: "low", status: "reported", area: "machines", title: "Cut finger",
  description: "", location: "", occurred_at: "2026-11-09T10:00:00Z", reporter: 3, reporter_name: "Asha",
  involved_user: 21, involved_name: "Ravi", involved_note: "", sponsor_user: null, machine: 12, room: 5, event: 9, loan: 30,
  booking: 40, repair_issue: 50, guest_pass: null, triaged_by: null, resolution_note: "", closed_at: null,
  created_at: "2026-11-09T10:05:00Z", updated_at: "2026-11-09T10:05:00Z", actions: [], ...overrides,
});
const page = (rows: Incident[]) => ({ count: rows.length, next: null, previous: null, results: rows });

function show(path: string, tabs: string[]) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={[path]}><AllowedTabsContext.Provider value={tabs}>
      <IncidentRegister makerspace={{ id: 4 }} />
    </AllowedTabsContext.Provider></MemoryRouter></QueryClientProvider>);
}

describe("incident cross-links (MC12, EB9)", () => {
  beforeEach(() => {
    api.staffRequest.mockReset();
    api.staffRequest.mockImplementation((path: string) => Promise.resolve(path.includes("saved-views") ? page([])
      : path.includes("/assignees") ? { results: [] } : path.startsWith("/admin/incidents/") ? incident() : page([incident(), incident({ id: 8, machine: 77, title: "Other machine" })])));
  });

  it("links every linked record into the area that owns it, when the viewer can open that area", async () => {
    show("/m/lab/admin/incidents?incident=7", ["machines", "events", "bookings", "requests", "repairs", "members"]);
    expect(await screen.findByRole("link", { name: "Machine #12" })).toHaveAttribute("href", "/m/lab/admin/machines?machine=12");
    expect(screen.getByRole("link", { name: "Event #9" })).toHaveAttribute("href", "/m/lab/admin/events?event=9");
    expect(screen.getByRole("link", { name: "Booking #40" })).toHaveAttribute("href", "/m/lab/admin/bookings?space=5&booking=40&bookingTab=requests");
    expect(screen.getByRole("link", { name: "Loan #30" })).toHaveAttribute("href", "/m/lab/admin/requests?id=30");
    expect(screen.getByRole("link", { name: "Repair job #50" })).toHaveAttribute("href", "/m/lab/admin/repairs?issue=50");
    expect(screen.getByRole("link", { name: "Ravi" })).toHaveAttribute("href", "/m/lab/admin/members?member=21");
  });

  it("keeps plain text for areas the viewer does not manage (decision 224)", async () => {
    show("/m/lab/admin/incidents?incident=7", ["machines"]);
    expect(await screen.findByRole("link", { name: "Machine #12" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Event #9" })).toBeNull();
    expect(screen.getByText("#9")).toBeInTheDocument();
    // C30: without the Members tab a person opens the member 360 drawer on this same tab.
    expect(screen.getByRole("link", { name: "Ravi" }).getAttribute("href")).toMatch(/^\/m\/lab\/admin\/incidents\?.*member=/);
  });

  it("narrows the register to a linked record and lets staff clear it", async () => {
    show("/m/lab/admin/incidents?machine=12", []);
    expect(await screen.findByText("Cut finger")).toBeInTheDocument();
    expect(screen.queryByText("Other machine")).toBeNull();
    expect(api.staffRequest).toHaveBeenCalledWith("/admin/makerspaces/4/incidents?machine=12&page=1");
    expect(screen.getByText("Showing incidents linked to machine #12.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Show all incidents" }));
    await waitFor(() => expect(api.staffRequest).toHaveBeenCalledWith("/admin/makerspaces/4/incidents?page=1"));
  });

  it("keeps its filters in the URL and offers saved views (MC10)", async () => {
    show("/m/lab/admin/incidents?severity=high", []);
    await waitFor(() => expect(api.staffRequest).toHaveBeenCalledWith("/admin/makerspaces/4/incidents?severity=high&page=1"));
    expect(screen.getByRole("combobox", { name: "Severity" })).toHaveValue("high");
    expect(api.staffRequest).toHaveBeenCalledWith(expect.stringContaining("/admin/makerspaces/4/saved-views?entity=incidents"));
  });
});
