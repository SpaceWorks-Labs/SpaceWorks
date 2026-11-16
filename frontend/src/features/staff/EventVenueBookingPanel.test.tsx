import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

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

function show(actions = ["manage_events", "manage_bookings"], modules = ["events", "bookings"]) {
  const client = new QueryClient();
  const view = (active: boolean) => <QueryClientProvider client={client}>
    <StaffListContext.Provider value={{ ownerName: "", canShare: false, actorId: 7, actions,
      makerspace: { id: 3, enabled_modules: modules } }}>
      <EventVenueBookingPanel makerspaceId={3} eventId={4} readOnly={false} active={active} />
    </StaffListContext.Provider>
  </QueryClientProvider>;
  const mounted = render(view(true));
  return { setActive: (active: boolean) => mounted.rerender(view(active)), client };
}

it("keeps the exact billing-confirmed link body across a lost response and renders neutral linked state", async () => {
  mock.request.mockReset();
  let attempt = 0;
  mock.request.mockImplementation(async (path: string, init?: RequestInit) => {
    if (path === route && init?.method === "POST") {
      if (++attempt === 1) throw new Error("response lost");
      return { state: "linked", replayed: true };
    }
    if (path === route) return attempt < 2 ? absent : { ...absent, state: "linked", booking_id: 8,
      booking_window: window, billing_owner: "booking", sync: "different", reservation_state: "unavailable" };
    if (path === "/admin/makerspaces/3/spaces/?page=1") return page([
      { id: 6, makerspace_id: 3, name: "Meeting room", kind: "meeting", is_active: true, staff_permissions: ["manage_reservations"] },
      { id: 7, makerspace_id: 3, name: "Restricted room", kind: "meeting", is_active: true },
    ]);
    if (path === "/admin/spaces/6/bookings/?page=1&ordering=starts_at") return page([
      { id: 8, space_id: 6, status: "pending", name: "Private Booker", ...window },
    ]);
    throw new Error("Unexpected route");
  });
  const { setActive, client } = show();
  expect(mock.request).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Manage venue booking" }));
  await screen.findByRole("option", { name: "Meeting room" });
  expect(screen.queryByText("Restricted room")).toBeNull();
  fireEvent.change(screen.getByRole("combobox", { name: "Room" }), { target: { value: "6" } });
  await screen.findByRole("option", { name: /#8.*Pending/ });
  expect(screen.queryByText("Private Booker")).toBeNull();
  fireEvent.change(screen.getByRole("combobox", { name: "Booking" }), { target: { value: "8" } });
  const link = screen.getByRole("button", { name: "Link booking" });
  expect(link).toBeDisabled();
  fireEvent.click(screen.getByRole("checkbox", { name: /confirm that the booking owns venue billing/i }));
  fireEvent.click(link);
  await screen.findByRole("button", { name: "Retry the same link" });
  setActive(false);
  const beforeHiddenInvalidation = mock.request.mock.calls.length;
  await client.invalidateQueries({ queryKey: ["event-venue-booking"] });
  expect(mock.request).toHaveBeenCalledTimes(beforeHiddenInvalidation);
  setActive(true);
  fireEvent.click(await screen.findByRole("button", { name: "Retry the same link" }));
  expect(await screen.findByText(/Booking #8 is linked/)).toBeVisible();
  expect(screen.getByText(/no longer reserves the room/)).toBeVisible();
  expect(screen.getByText(/times differ/)).toBeVisible();
  const bodies = mock.request.mock.calls.filter(([path, init]) => path === route && init?.method === "POST")
    .map(([, init]) => init.body);
  expect(bodies).toHaveLength(2);
  expect(bodies[0]).toBe(bodies[1]);
  expect(JSON.parse(bodies[0])).toEqual({
    operation_id: expect.any(String), expected_generation: null, expected_revision: 0,
    expected_events_epoch: absent.events_epoch, expected_bookings_epoch: absent.bookings_epoch,
    confirm_billing_owner: "booking", existing_booking_id: 8,
  });
});

it.each([
  [["manage_events"], ["events", "bookings"]],
  [["manage_bookings"], ["events", "bookings"]],
  [["manage_events", "manage_bookings"], ["events"]],
  [["manage_events", "manage_bookings"], ["bookings"]],
])("omits the booking panel without both grants and modules", (actions, modules) => {
  mock.request.mockReset();
  show(actions, modules);
  expect(screen.queryByRole("button", { name: "Manage venue booking" })).toBeNull();
  expect(mock.request).not.toHaveBeenCalled();
});

it("shows retained unavailability without requesting room choices or exposing an old target", async () => {
  mock.request.mockReset().mockResolvedValue({ ...absent, state: "booking_unavailable" });
  show();
  fireEvent.click(screen.getByRole("button", { name: "Manage venue booking" }));
  expect(await screen.findByText(/original linked booking is unavailable/i)).toBeVisible();
  expect(screen.queryByRole("combobox")).toBeNull();
  expect(mock.request).toHaveBeenCalledTimes(1);
});
