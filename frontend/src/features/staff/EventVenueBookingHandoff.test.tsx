import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

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
const slot = { starts_at: "2026-11-20T10:00:00Z", ends_at: "2026-11-20T12:00:00Z" };
const epochs = { events_epoch: "00000000-0000-4000-8000-000000000001", bookings_epoch: "00000000-0000-4000-8000-000000000002" };
const absent = { generation: null, revision: 0, ...epochs, state: "absent", booking_id: null, billing_owner: null,
  event_window: slot, booking_window: null, sync: "unavailable", fee_state: "none" };
const page = (results: unknown[]) => ({ results, previous: null, next: null });
const room = { id: 6, makerspace_id: 3, name: "Meeting room", kind: "meeting", is_active: true,
  approval_mode: "approve", custom_form: null, staff_permissions: ["manage_reservations"] };
const quote = { charges: "tracked", quote: { currency: "usd", total: "12.50", discount_total: "0.00" }, price_confirmation: "b".repeat(64) };
const members = page([{ member_id: 9, display_name: "Ada" }]);

function show() {
  const client = new QueryClient();
  render(<QueryClientProvider client={client}>
    <StaffListContext.Provider value={{ ownerName: "", canShare: false, actorId: 7, actions: ["manage_events", "manage_bookings"],
      makerspace: { id: 3, enabled_modules: ["events", "bookings"] } }}>
      <EventVenueBookingPanel makerspaceId={3} eventId={4} readOnly={false} />
    </StaffListContext.Provider>
  </QueryClientProvider>);
}

const posts = (path: string) => mock.request.mock.calls.filter(([url, init]) => url === path && init?.method === "POST")
  .map(([, init]) => JSON.parse(init.body));

beforeEach(() => { mock.request.mockReset(); });

it("creates a booking at the confirmed price, then links it only after explicit confirmation", async () => {
  let linked = false;
  mock.request.mockImplementation(async (path: string, init?: RequestInit) => {
    if (path === route && init?.method === "POST") { linked = true; return { state: "linked" }; }
    if (path === route) return linked ? { ...absent, state: "linked", booking_id: 31, current_booking_id: 31, booking_window: slot,
      billing_owner: "booking", reservation_state: "pending", sync: "matched", replaceable: false, history: [] } : absent;
    if (path === "/admin/makerspaces/3/spaces/?page=1") return page([room]);
    if (path === "/admin/spaces/6/bookings/?page=1&ordering=starts_at") return page([]);
    if (path === "/admin/spaces/6/eligible-members/?page=1") return members;
    if (path === "/admin/spaces/6/bookings/quote/") return quote;
    if (path === "/admin/spaces/6/bookings/" && init?.method === "POST") return { id: 31, space_id: 6, status: "pending" };
    throw new Error(`Unexpected route ${path}`);
  });
  show();
  fireEvent.click(screen.getByRole("button", { name: "Manage venue booking" }));
  await screen.findByRole("option", { name: "Meeting room" });
  fireEvent.change(screen.getByRole("combobox", { name: "Room" }), { target: { value: "6" } });
  fireEvent.click(await screen.findByRole("button", { name: "Book this room for a member" }));
  fireEvent.change(await screen.findByRole("combobox", { name: "Member" }), { target: { value: "9" } });
  await screen.findByRole("option", { name: "Ada" });
  fireEvent.change(screen.getByRole("combobox", { name: "Member" }), { target: { value: "9" } });
  fireEvent.change(screen.getByLabelText("Starts (your local time)"), { target: { value: "2026-11-20T10:00" } });
  fireEvent.change(screen.getByLabelText("Ends (your local time)"), { target: { value: "2026-11-20T12:00" } });
  fireEvent.click(screen.getByRole("button", { name: "Review price" }));
  expect(await screen.findByText("Room price: $12.50")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Confirm price and create booking" }));
  expect(await screen.findByText(/Booking #31 was created\. It is not linked/)).toBeInTheDocument();
  expect(posts("/admin/spaces/6/bookings/")[0]).toMatchObject({ member_id: 9, price_confirmation: quote.price_confirmation });
  expect(posts(route)).toHaveLength(0);
  const link = screen.getByRole("button", { name: "Link booking" });
  expect(link).toBeDisabled();
  fireEvent.click(screen.getByRole("checkbox", { name: /confirm that the booking owns venue billing/i }));
  fireEvent.click(link);
  expect(await screen.findByText(/Booking #31 is linked/)).toBeVisible();
  expect(posts(route)).toEqual([expect.objectContaining({ existing_booking_id: 31, confirm_billing_owner: "booking" })]);
  expect(posts("/admin/spaces/6/bookings/")).toHaveLength(1);
});

it("replaces a rejected linked booking at a confirmed price and shows the retained history", async () => {
  let replaced = false;
  const rejected = { ...absent, state: "linked", generation: "00000000-0000-4000-8000-000000000003", revision: 1,
    booking_id: 12, current_booking_id: 12, booking_window: slot, billing_owner: "booking",
    reservation_state: "unavailable", sync: "matched", replaceable: true, history: [] };
  mock.request.mockImplementation(async (path: string, init?: RequestInit) => {
    if (path === `${route}/replacement`) { replaced = true; return { booking_id: 40, replaces_booking_id: 12, status: "pending" }; }
    if (path === route) return replaced ? { ...rejected, current_booking_id: 40, reservation_state: "pending", replaceable: false,
      history: [{ booking_id: 12, status: "rejected" }] } : rejected;
    if (path === "/admin/makerspaces/3/spaces/?page=1") return page([room]);
    if (path === "/admin/spaces/6/eligible-members/?page=1") return members;
    if (path === "/admin/spaces/6/bookings/quote/") return quote;
    throw new Error(`Unexpected route ${path} ${init?.method ?? "GET"}`);
  });
  show();
  fireEvent.click(screen.getByRole("button", { name: "Manage venue booking" }));
  expect(await screen.findByText(/Booking #12 is linked/)).toBeVisible();
  await screen.findByRole("option", { name: "Meeting room" });
  fireEvent.change(screen.getByRole("combobox", { name: "Room" }), { target: { value: "6" } });
  await screen.findByRole("option", { name: "Ada" });
  fireEvent.change(screen.getByRole("combobox", { name: "Member" }), { target: { value: "9" } });
  fireEvent.click(screen.getByRole("button", { name: "Review price" }));
  expect(await screen.findByText("Approval uses this price if booking charges apply.")).toBeInTheDocument();
  expect(posts(`${route}/replacement`)).toHaveLength(0);
  fireEvent.click(screen.getByRole("button", { name: "Confirm price and replace booking" }));
  expect(await screen.findByText(/Booking #40 is linked/)).toBeVisible();
  expect(screen.getByText(/Earlier bookings kept on record: #12 \(rejected\)/)).toBeVisible();
  await waitFor(() => expect(posts(`${route}/replacement`)).toEqual([{
    expected_booking_id: 12, space_id: 6, member_id: 9,
    starts_at: new Date(slot.starts_at).toISOString(), ends_at: new Date(slot.ends_at).toISOString(),
    price_confirmation: quote.price_confirmation,
  }]));
});
