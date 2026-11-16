import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AllowedTabsContext } from "../areaOverview/allowedTabsContext";
import { BookingRowLinks } from "../bookingLinks/BookingRowLinks";
import type { Booking } from "../bookingsApi";
import { GuestCsvButton } from "../eventRoster/GuestCsvButton";
import { RegistrationFiltersBar } from "../eventRoster/RegistrationFilters";
import { StaffListContext } from "../StaffListContext";
import { EventCrossLinks } from "./EventCrossLinks";

const api = vi.hoisted(() => ({ staffRequest: vi.fn(), staffRequestBlob: vi.fn() }));
vi.mock("../../../lib/api", async original => ({ ...(await original<object>()), staffRequest: api.staffRequest, staffRequestBlob: api.staffRequestBlob }));

function wrap(node: ReactNode, { tabs = [] as string[], actions = ["manage_events"], modules = ["events", "request_workflow"], features = ["membership.guest_passes"] } = {}) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={["/m/lab/admin/events"]}>
      <StaffListContext.Provider value={{ ownerName: "em", canShare: false, actions, makerspace: { id: 4, enabled_modules: modules, enabled_features: features } }}>
        <AllowedTabsContext.Provider value={tabs}>{node}</AllowedTabsContext.Provider>
      </StaffListContext.Provider>
    </MemoryRouter></QueryClientProvider>);
}
const empty = { count: 0, next: null, previous: null, results: [] };

describe("event cross-links (EB9-EB11, 242(g))", () => {
  beforeEach(() => { api.staffRequest.mockReset(); api.staffRequest.mockImplementation(() => new Promise(() => {})); });

  it("shows the event's loans and guest passes read-only to an Event Manager", async () => {
    api.staffRequest.mockImplementation((path: string) => Promise.resolve(path.endsWith("/loans/")
      ? { enabled: true, results: [{ request_id: 30, status: "issued", holder: "Asha", issued_at: null, due_at: "2026-11-20T10:00:00Z",
        items: [{ product_name: "Soldering iron", requested: 2, issued: 2, returned: 0 }] }] }
      : path.endsWith("/guest-passes/") ? { enabled: true, results: [{ id: 3, kind: "event", status: "active", holder: "guest1", valid_until: "2026-11-21T10:00:00Z" }] }
      : { count: 1, next: null, previous: null, results: [{ id: 9, event: 7, status: "reported" }] }));
    wrap(<EventCrossLinks makerspaceId={4} eventId={7} />, { tabs: ["incidents"] });
    expect(await screen.findByText("Soldering iron ×2")).toBeInTheDocument();
    expect(screen.getByText("guest1")).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: /Incidents/ })).toHaveAttribute("href", "/m/lab/admin/incidents?event=7");
    expect(screen.queryByRole("button", { name: /issue|return/i })).toBeNull();
    expect(api.staffRequest).toHaveBeenCalledWith("/admin/events/7/loans/", expect.anything());
  });

  it("leaves loans to the equipment desk for issue staff and hides switched-off lists", async () => {
    api.staffRequest.mockImplementation((path: string) => Promise.resolve(path.endsWith("/guest-passes/") ? { enabled: false, results: [] } : empty));
    const { container } = wrap(<EventCrossLinks makerspaceId={4} eventId={7} />, { actions: ["manage_events", "issue_request"] });
    await waitFor(() => expect(api.staffRequest).toHaveBeenCalledWith("/admin/events/7/guest-passes/", expect.anything()));
    expect(api.staffRequest).not.toHaveBeenCalledWith("/admin/events/7/loans/", expect.anything());
    await waitFor(() => expect(container.textContent).toBe(""));
  });

  it("filters the roster and exports the matching guests as CSV (EB1, EB5)", async () => {
    const onChange = vi.fn();
    render(<RegistrationFiltersBar value={{}} onChange={onChange} tickets={[{ id: 2, name: "Early bird" } as never]} />);
    fireEvent.change(screen.getByRole("combobox", { name: "Ticket" }), { target: { value: "2" } });
    expect(onChange).toHaveBeenCalledWith({ ticket_type: "2" });
    api.staffRequestBlob.mockResolvedValue(new Blob(["id"]));
    URL.createObjectURL = vi.fn(() => "blob:x"); URL.revokeObjectURL = vi.fn();
    wrap(<GuestCsvButton eventId={7} status="waitlisted" q="ann" />, { features: ["events.saved_views"] });
    fireEvent.click(screen.getByRole("button", { name: "Download these guests (CSV)" }));
    await waitFor(() => expect(api.staffRequestBlob).toHaveBeenCalledWith("/admin/events/7/lists/guests/export/?status=waitlisted&q=ann"));
  });

  it("hides the guest CSV while staff lists are switched off", () => {
    wrap(<GuestCsvButton eventId={7} />, { features: [] });
    expect(screen.queryByRole("button")).toBeNull();
  });
});

describe("booking cross-links (EB8, EB9, BK2)", () => {
  const booking = { id: 40, member_id: 21, linked_event: { kind: "event", event_id: 7, title: "Robot night" } } as Booking;

  it("links a booking to its event, its member and its incidents when the viewer manages them", () => {
    wrap(<BookingRowLinks booking={booking} />, { tabs: ["events", "members", "incidents"] });
    expect(screen.getByRole("link", { name: "Event: Robot night" })).toHaveAttribute("href", "/m/lab/admin/events?event=7");
    expect(screen.getByRole("link", { name: "Member activity" })).toHaveAttribute("href", "/m/lab/admin/members?member=21");
    expect(screen.getByRole("link", { name: "Incidents" })).toHaveAttribute("href", "/m/lab/admin/incidents?booking=40");
  });

  it("keeps the event as text for a Booking Manager without events", () => {
    wrap(<BookingRowLinks booking={booking} />, { tabs: ["bookings"] });
    expect(screen.getByText("Event: Robot night")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Event: Robot night" })).toBeNull();
    // C30: the member 360 opens as a drawer on the current tab when Members is not theirs.
    expect(screen.getByRole("link", { name: "Member activity" })).toHaveAttribute("href", "/m/lab/admin/events?member=21");
    expect(screen.queryByRole("link", { name: "Incidents" })).toBeNull();
  });
});
