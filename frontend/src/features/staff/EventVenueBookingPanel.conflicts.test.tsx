import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import { StructuredApiError } from "../../lib/api";
import { EventVenueBookingPanel } from "./EventVenueBookingPanel";
import { StaffListContext } from "./StaffListContext";

const mock = vi.hoisted(() => ({ request: vi.fn(), owner: "7" }));
vi.mock("../../lib/api", async original => ({
  ...await original<typeof import("../../lib/api")>(), staffRequest: mock.request,
}));
vi.mock("../../lib/api/sessionTokens", async original => ({
  ...await original<typeof import("../../lib/api/sessionTokens")>(), getSessionOwner: () => mock.owner,
}));
vi.mock("../inventory/useIntakeScope", () => ({ useIntakeScope: () => ({ context: "person", owner: mock.owner }) }));

const route = "/admin/makerspace/3/events/4/booking-link";
const window = { starts_at: "2026-11-20T10:00:00Z", ends_at: "2026-11-20T12:00:00Z" };
const absent = {
  generation: null, revision: 0, events_epoch: "00000000-0000-4000-8000-000000000001",
  bookings_epoch: "00000000-0000-4000-8000-000000000002", state: "absent", booking_id: null,
  billing_owner: null, event_window: window, booking_window: null, sync: "unavailable", fee_state: "none",
};
const page = (results: unknown[]) => ({ results, previous: null, next: null });

function show() {
  render(<QueryClientProvider client={new QueryClient()}>
    <StaffListContext.Provider value={{ ownerName: "", canShare: false, actorId: 7, actions: ["manage_events", "manage_bookings"],
      makerspace: { id: 3, enabled_modules: ["events", "bookings"] } }}>
      <EventVenueBookingPanel makerspaceId={3} eventId={4} readOnly={false} />
    </StaffListContext.Provider>
  </QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Manage venue booking" }));
}

it("shows the room's readiness for the event time before linking and explains an out-of-service refusal", async () => {
  mock.request.mockReset().mockImplementation(async (path: string, init?: RequestInit) => {
    if (path === route && init?.method === "POST") throw new StructuredApiError(409, { detail: "Booking decision cannot be applied.", code: "room_out_of_service" });
    if (path === route) return absent;
    if (path === "/admin/makerspaces/3/spaces/?page=1") return page([
      { id: 6, makerspace_id: 3, name: "Meeting room", kind: "meeting", is_active: true, staff_permissions: ["manage_reservations"] }]);
    if (path.startsWith("/admin/spaces/6/bookings/readiness/")) return { ready: false, maintenance_link: null,
      checks: [{ code: "room_outage", state: "blocked", detail: "This room is out of service for that time." }] };
    if (path === "/admin/spaces/6/bookings/?page=1&ordering=starts_at") return page([{ id: 8, space_id: 6, status: "confirmed", ...window }]);
    throw new Error(`Unexpected route ${path}`);
  });
  show();
  await screen.findByRole("option", { name: "Meeting room" });
  fireEvent.change(screen.getByRole("combobox", { name: "Room" }), { target: { value: "6" } });
  expect(await screen.findByText("This room is out of service at that time.")).toBeVisible();
  const readiness = mock.request.mock.calls.map(([path]) => String(path)).find(path => path.includes("/readiness/"));
  expect(readiness).toContain(`starts_at=${encodeURIComponent(new Date(window.starts_at).toISOString())}`);
  await screen.findByRole("option", { name: /#8/ });
  fireEvent.change(screen.getByRole("combobox", { name: "Booking" }), { target: { value: "8" } });
  fireEvent.click(screen.getByRole("checkbox", { name: /confirm that the booking owns venue billing/i }));
  fireEvent.click(screen.getByRole("button", { name: "Link booking" }));
  expect(await screen.findByText(/Room out of service: this room refuses bookings during the event/)).toBeVisible();
});

it("shows server conflicts on a linked reservation", async () => {
  mock.request.mockReset().mockResolvedValue({ ...absent, state: "linked", booking_id: 8, current_booking_id: 8,
    current_space_id: 6, booking_window: window, billing_owner: "booking", sync: "matched", reservation_state: "confirmed",
    event_status: "published", coverage: "covers", conflicts: [{ code: "room_out_of_service", severity: "block" }] });
  show();
  expect(await screen.findByText("Room out of service during this event")).toBeVisible();
  expect(screen.getByRole("link", { name: "Open the booking in Bookings" })).toBeVisible();
});
