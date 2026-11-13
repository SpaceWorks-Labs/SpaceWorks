import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import { StructuredApiError } from "../../lib/api";
import { EventVenueBookingPanel } from "./EventVenueBookingPanel";
import { StaffListContext } from "./StaffListContext";

const mock = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../lib/api", async original => ({ ...await original<typeof import("../../lib/api")>(), staffRequest: mock.request }));
vi.mock("../../lib/api/sessionTokens", async original => ({
  ...await original<typeof import("../../lib/api/sessionTokens")>(), getSessionOwner: () => "7",
}));
vi.mock("../inventory/useIntakeScope", () => ({ useIntakeScope: () => ({ context: "person", owner: "7" }) }));
vi.mock("./BookingReadiness", () => ({ StaffBookingReadiness: () => null }));
vi.mock("./EventWorkshopMachines", () => ({ EventWorkshopMachines: () => null }));

const route = "/admin/makerspace/3/events/4/booking-link";
const window = { starts_at: "2030-11-20T10:00:00Z", ends_at: "2030-11-20T12:00:00Z" };
const absent = { generation: null, revision: 0, events_epoch: "e", bookings_epoch: "b", state: "absent", booking_id: null,
  billing_owner: null, event_window: window, booking_window: null, sync: "unavailable", fee_state: "none" };
const page = (results: unknown[]) => ({ results, previous: null, next: null });

it("offers 'link anyway' for a partial booking and shows capacity warnings after linking", async () => {
  mock.request.mockImplementation(async (path: string, init?: RequestInit) => {
    if (path === route && init?.method === "POST") {
      if (!JSON.parse(String(init.body)).allow_partial_coverage) throw new StructuredApiError(409, { code: "booking_does_not_cover_event", detail: "partial" });
      return { state: "linked", warnings: [{ code: "event_capacity_above_room", event_capacity: 40, room_capacity: 20 }] };
    }
    if (path === route) return absent;
    if (path.startsWith("/admin/makerspaces/3/spaces/")) return page([{ id: 6, makerspace_id: 3, name: "Hall", kind: "meeting", is_active: true, staff_permissions: ["manage_reservations"] }]);
    if (path.startsWith("/admin/spaces/6/bookings/")) return page([{ id: 8, space_id: 6, status: "confirmed", starts_at: window.starts_at, ends_at: "2030-11-20T11:00:00Z" }]);
    throw new Error(`unexpected ${path}`);
  });
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <StaffListContext.Provider value={{ ownerName: "", canShare: false, actorId: 7, actions: ["manage_events", "manage_bookings"], makerspace: { id: 3, enabled_modules: ["events", "bookings"] } }}>
      <EventVenueBookingPanel makerspaceId={3} eventId={4} readOnly={false} />
    </StaffListContext.Provider></QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Manage venue booking" }));
  await screen.findByRole("option", { name: "Hall" });
  fireEvent.change(screen.getByRole("combobox", { name: "Room" }), { target: { value: "6" } });
  await screen.findByRole("option", { name: /#8/ });
  fireEvent.change(screen.getByRole("combobox", { name: "Booking" }), { target: { value: "8" } });
  fireEvent.click(screen.getByRole("checkbox", { name: /owns venue billing/ }));
  fireEvent.click(screen.getByRole("button", { name: "Link booking" }));
  expect(await screen.findByText(/does not cover the whole event time/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Link anyway (partial coverage)" }));
  expect(await screen.findByText("The event allows 40 places but the room holds 20.")).toBeInTheDocument();
  await waitFor(() => {
    const bodies = mock.request.mock.calls.filter(([path, init]) => path === route && init?.method === "POST").map(([, init]) => JSON.parse(init.body));
    expect(bodies).toHaveLength(2);
    expect(bodies[1]).toMatchObject({ existing_booking_id: 8, allow_partial_coverage: true });
    expect(bodies[1].operation_id).not.toBe(bodies[0].operation_id);
  });
});
