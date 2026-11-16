// Open items A19, A20, A21, A22, A23: cross-space drawers, read-only tickets, the waiting queue, deep links.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AllowedTabsContext } from "./areaOverview/allowedTabsContext";
import { eventDrawerSurfaces } from "./eventDrawerTabs";
import { eventAccess } from "./eventStaffPermissions";
import type { StaffEvent } from "./eventsApi";
import { StaffListContext } from "./StaffListContext";
import { useContext } from "react";

function RelatedFactsPanelProbe() { const { makerspace } = useContext(StaffListContext); return <p>Booking drawer in space {makerspace?.id}</p>; }

const { request, bootstrap, drawer } = vi.hoisted(() => ({ request: vi.fn(), bootstrap: vi.fn(), drawer: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...(await vi.importActual<object>("../../lib/api")), staffRequest: request }));
vi.mock("../inventory/usePublicInventory", () => ({ useTenantBootstrap: bootstrap }));
vi.mock("./BookingDrawer", () => ({ BookingDrawer: () => <RelatedFactsPanelProbe /> }));
vi.mock("./EventDrawer", () => ({ EventDrawer: (props: { enabledFeatures: string[]; enabledModules: string[] }) => {
  drawer(props); return <p>Drawer with {props.enabledModules.join(",")}</p>;
} }));

import { EventRegistrationQueue } from "./EventRegistrationQueue";
import { EventTicketsPanel } from "./EventTicketsPanel";
import { EventVenueSummary } from "./EventVenueSummary";
import { BookingAgenda } from "./BookingAgenda";
import { GrantedBookingSpacesPanel } from "./GrantedBookingSpacesPanel";
import { RelatedFactsPanel } from "./RelatedFactsPanel";
import { ScopedEventDrawer } from "./ScopedEventDrawer";
import { SpaceScope } from "./SpaceScope";

function wrap(node: ReactNode, { tabs = [] as string[], space = { id: 1, enabled_modules: ["events"] } } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter><AllowedTabsContext.Provider value={tabs}>
    <StaffListContext.Provider value={{ ownerName: "sam", canShare: false, actorId: 5, actions: ["manage_events"], makerspace: space }}>
      {node}</StaffListContext.Provider></AllowedTabsContext.Provider></MemoryRouter></QueryClientProvider>);
}

beforeEach(() => {
  request.mockReset(); drawer.mockReset();
  bootstrap.mockReturnValue({ data: { modules: ["events", "bookings"], features: ["events.volunteering"] }, isLoading: false });
});

describe("A19/A20 cross-space event drawers", () => {
  it("hides related activity for another space until the drawer is scoped to it", () => {
    const { unmount } = wrap(<RelatedFactsPanel tenant={9} kind="event" id={3} />);
    expect(screen.queryByRole("button", { name: "View related activity" })).toBeNull();
    unmount();
    wrap(<SpaceScope makerspaceId={9} slug="north"><RelatedFactsPanel tenant={9} kind="event" id={3} /></SpaceScope>);
    expect(screen.getByRole("button", { name: "View related activity" })).toBeInTheDocument();
    expect(bootstrap).toHaveBeenCalledWith("north", true);
  });

  it("opens an organized or assigned event with its own space's switches", () => {
    wrap(<ScopedEventDrawer slug="north" eventId={3} makerspaceId={9} onClose={() => undefined} />);
    expect(screen.getByText("Drawer with events,bookings")).toBeInTheDocument();
    expect(drawer).toHaveBeenCalledWith(expect.objectContaining({ enabledFeatures: ["events.volunteering"], eventId: 3, makerspaceId: 9 }));
  });
});

describe("A21 read-only ticket types", () => {
  const event = { status: "published", ticketing_features: ["events.ticket_types"] } as unknown as StaffEvent;
  it("opens Tickets read-only for manage_registrations and editable for managers", () => {
    const grantee = eventDrawerSurfaces(event, eventAccess({ can_manage_staff: false, staff_permissions: ["manage_registrations"] }));
    expect(grantee.sections.tickets).toBe(true);
    expect(grantee.ticketTypesReadOnly).toBe(true);
    const manager = eventDrawerSurfaces(event, eventAccess({ can_manage_staff: true, staff_permissions: [] }));
    expect(manager.ticketTypesReadOnly).toBe(false);
    const checkIn = eventDrawerSurfaces(event, eventAccess({ can_manage_staff: false, staff_permissions: ["check_in"] }));
    expect(checkIn.sections.tickets).toBe(false);
  });

  it("lists ticket types without the add form when read-only", async () => {
    request.mockResolvedValue({ count: 1, next: null, previous: null, results: [{ id: 1, name: "Early bird", amount: "5.00", audience: "public", capacity: 10, sales_start_at: null, sales_end_at: null, registration_count: 3 }] });
    wrap(<EventTicketsPanel eventId={4} readOnly />);
    expect(await screen.findByText("Early bird")).toBeInTheDocument();
    expect(screen.getByText(/3 of 10 taken/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add ticket type" })).toBeNull();
    expect(screen.getByText(/Ask an event manager/)).toBeInTheDocument();
  });
});

describe("A22 registrations waiting on staff", () => {
  const rows = [
    { id: 11, status: "pending_approval", created_at: "2030-01-01T10:00:00Z", name: "Ana", event: { id: 4, title: "Soldering", starts_at: "2030-02-01T10:00:00Z", capacity: 10 } },
    { id: 12, status: "waitlisted", created_at: "2030-01-02T10:00:00Z", name: "Ben", event: { id: 5, title: "Laser basics", starts_at: "2030-02-02T10:00:00Z", capacity: 1 } },
  ];
  it("approves and promotes through the per-registration routes", async () => {
    request.mockImplementation(async (path: string) => path.includes("event-registration-queue")
      ? { count: 2, next: null, previous: null, results: rows } : {});
    const open = vi.fn();
    wrap(<EventRegistrationQueue makerspaceId={7} onOpenEvent={open} />);
    expect(await screen.findByText("Ana")).toBeInTheDocument();
    expect(request).toHaveBeenCalledWith("/admin/makerspace/7/event-registration-queue?page=1");
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/event-registrations/11/approve/", { method: "POST", body: "{}" }));
    fireEvent.click(screen.getByRole("button", { name: "Give a place" }));
    await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/event-registrations/12/promote/", { method: "POST", body: "{}" }));
    fireEvent.click(screen.getAllByRole("button", { name: "Open event" })[1]);
    expect(open).toHaveBeenCalledWith(5);
  });

  it("filters the waitlist and shows a plain empty state", async () => {
    request.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    wrap(<EventRegistrationQueue makerspaceId={7} onOpenEvent={vi.fn()} />);
    expect(await screen.findByText(/Nothing is waiting/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("radio", { name: "Waitlist" }));
    expect(await screen.findByText("No one is on a waitlist.")).toBeInTheDocument();
    expect(request).toHaveBeenCalledWith("/admin/makerspace/7/event-registration-queue?page=1&status=waitlisted");
  });

  it("shows an error when the queue cannot load", async () => {
    request.mockRejectedValue(new Error("Queue down"));
    wrap(<EventRegistrationQueue makerspaceId={7} onOpenEvent={vi.fn()} />);
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});

describe("A23 event to room booking link", () => {
  const panel = { venue: { state: "confirmed", booking_id: 31, space_id: 6, space_name: "Hall" }, warnings: [], can_manage_booking: false };
  it("links to the booking only for someone who may open Bookings", async () => {
    request.mockResolvedValue(panel);
    const { unmount } = wrap(<EventVenueSummary makerspaceId={1} eventId={2} />, { tabs: ["bookings"] });
    const link = await screen.findByRole("link", { name: "Open the room booking" });
    expect(link.getAttribute("href")).toContain("booking=31");
    expect(link.getAttribute("href")).toContain("space=6");
    unmount();
    wrap(<EventVenueSummary makerspaceId={1} eventId={2} />, { tabs: [] });
    expect(await screen.findByText(/Hall is booked/)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Open the room booking" })).toBeNull();
  });
});

describe("A19 assigned booking resources and A23 agenda event link", () => {
  it("scopes an assigned resource's drawer to its own space", async () => {
    request.mockResolvedValue({ count: 1, next: null, previous: null, results: [{ id: 2, makerspace_id: 9, name: "Hall", staff_permissions: [] }] });
    wrap(<GrantedBookingSpacesPanel grants={[{ space_id: 2, makerspace_id: 9, makerspace_slug: "north", name: "Hall", source: "booking_grant", permissions: [] }]} />);
    fireEvent.click(await screen.findByRole("button", { name: /Hall/ }));
    expect(await screen.findByText("Booking drawer in space 9")).toBeInTheDocument();
    expect(bootstrap).toHaveBeenCalledWith("north", true);
  });

  it("links an agenda booking to the event it holds the room for", async () => {
    request.mockImplementation(async (path: string) => path.includes("bookings")
      ? { count: 1, next: null, previous: null, results: [{ id: 3, name: "Workshop room", status: "confirmed", starts_at: "2030-01-01T10:00:00Z", ends_at: "2030-01-01T12:00:00Z",
        linked_event: { kind: "event", event_id: 44, title: "Soldering" } }] }
      : { count: 0, next: null, previous: null, results: [] });
    wrap(<BookingAgenda spaceId={2} onOpen={vi.fn()} />, { tabs: ["events"] });
    const link = await screen.findByRole("link", { name: "Open event" });
    expect(link.getAttribute("href")).toContain("event=44");
  });
});
