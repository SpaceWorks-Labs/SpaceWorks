import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { linkedEventText } from "./BookingAgenda";
import { EventVenueBookingPanel } from "./EventVenueBookingPanel";
import { StaffBookingAvailability, toLocalInput } from "./StaffBookingAvailability";
import { StaffBookingForm } from "./StaffBookingForm";
import { StaffListContext } from "./StaffListContext";
import type { BookableSpace } from "./bookingsApi";

const mock = vi.hoisted(() => ({ request: vi.fn(), owner: "7" }));
vi.mock("../../lib/api", async original => ({
  ...await original<typeof import("../../lib/api")>(), staffRequest: mock.request,
}));
vi.mock("../../lib/api/sessionTokens", async original => ({
  ...await original<typeof import("../../lib/api/sessionTokens")>(), getSessionOwner: () => mock.owner,
}));
vi.mock("../inventory/useIntakeScope", () => ({ useIntakeScope: () => ({ context: "person", owner: mock.owner }) }));
vi.mock("./staffBookingApi", () => ({
  useBookingEligibleMembers: () => ({ data: { results: [{ member_id: 9, display_name: "Ada" }], next: null, previous: null }, isLoading: false, error: null }),
  useStaffCreateBooking: () => ({ mutate: vi.fn(), isPending: false, isSuccess: false, error: null }),
  previewStaffBookingPrice: vi.fn(),
}));

const slot = { starts_at: "2026-11-20T10:00:00Z", ends_at: "2026-11-20T12:00:00Z" };
const calendar = {
  space_id: 6, timezone: "Asia/Kolkata", range_starts_at: "2026-11-19T18:30:00Z", range_ends_at: "2026-11-20T18:30:00Z",
  opening_intervals: [{ starts_at: "2026-11-20T03:30:00Z", ends_at: "2026-11-20T12:30:00Z" }],
  busy: [
    { booking_id: 31, starts_at: "2026-11-20T09:45:00Z", ends_at: "2026-11-20T11:00:00Z", label: { kind: "event", event_id: 4, title: "Robotics night", event_status: "published" } },
    { booking_id: 32, starts_at: "2026-11-20T11:00:00Z", ends_at: "2026-11-20T11:30:00Z", label: { kind: "reserved" } },
  ],
  pending: [{ booking_id: 33, starts_at: "2026-11-20T06:00:00Z", ends_at: "2026-11-20T07:00:00Z", label: { kind: "booking" } }],
  requested: { within_rules: true, rule_detail: "", conflict: true, holds_room_on_create: true },
};
const availabilityPath = (window: { starts_at: string; ends_at: string }) =>
  `/admin/spaces/6/bookings/availability/?${new URLSearchParams({
    starts_at: new Date(toLocalInput(window.starts_at)).toISOString(), ends_at: new Date(toLocalInput(window.ends_at)).toISOString() })}`;

beforeEach(() => { mock.request.mockReset(); });

it("shows the room's Bookings calendar with event, reserved and pending labels and refuses a conflict up front", async () => {
  mock.request.mockResolvedValue(calendar);
  render(<StaffBookingAvailability spaceId={6} start={toLocalInput(slot.starts_at)} end={toLocalInput(slot.ends_at)} />);
  expect(await screen.findByText("This time overlaps a confirmed booking. The booking will be refused.")).toBeInTheDocument();
  expect(mock.request).toHaveBeenCalledWith(availabilityPath(slot), expect.any(Object));
  const booked = screen.getByRole("list", { name: "Booked times" });
  expect(within(booked).getByText(/Event: Robotics night/)).toBeInTheDocument();
  expect(within(booked).getByText(/Reserved/)).toBeInTheDocument();
  expect(within(screen.getByRole("list", { name: "Pending bookings" })).getByText(/Booked/)).toBeInTheDocument();
  expect(screen.getByText(/Asia\/Kolkata/)).toBeInTheDocument();
});

it("explains that an approval room is refused at approval, not on create", async () => {
  mock.request.mockResolvedValue({ ...calendar, requested: { ...calendar.requested, holds_room_on_create: false } });
  render(<StaffBookingAvailability spaceId={6} start={toLocalInput(slot.starts_at)} end={toLocalInput(slot.ends_at)} />);
  expect(await screen.findByText(/Approval will be refused while it does/)).toBeInTheDocument();
});

it("prefills the staff booking form with the event window and checks that window", async () => {
  mock.request.mockImplementation(async (path: string) => path.includes("/availability/")
    ? { ...calendar, busy: [], requested: { ...calendar.requested, conflict: false } }
    : { ready: true, checks: [], maintenance_link: null });
  const space = { id: 6, makerspace_id: 3, custom_form: null, approval_mode: "instant" } as unknown as BookableSpace;
  render(<StaffBookingForm makerspaceId={3} space={space} initialWindow={slot} />);
  expect(screen.getByLabelText("Starts (your local time)")).toHaveValue(toLocalInput(slot.starts_at));
  expect(screen.getByLabelText("Ends (your local time)")).toHaveValue(toLocalInput(slot.ends_at));
  expect(await screen.findByText("The room is free at this time.")).toBeInTheDocument();
  expect(mock.request).toHaveBeenCalledWith(availabilityPath(slot), expect.any(Object));
});

const route = "/admin/makerspace/3/events/4/booking-link";
const linked = {
  generation: "00000000-0000-4000-8000-000000000009", revision: 1, events_epoch: "00000000-0000-4000-8000-000000000001",
  bookings_epoch: "00000000-0000-4000-8000-000000000002", state: "linked", booking_id: 31, current_booking_id: 31,
  current_space_id: 6, billing_owner: "booking", event_window: slot, booking_window: slot, reservation_state: "confirmed",
  sync: "matched", coverage: "covers", event_status: "published", fee_state: "none", replaceable: false, history: [],
};

async function panel(link: Record<string, unknown>) {
  mock.request.mockImplementation(async (path: string) => {
    if (path === route) return link;
    throw new Error("Unexpected route");
  });
  render(<QueryClientProvider client={new QueryClient()}>
    <StaffListContext.Provider value={{ ownerName: "", canShare: false, actorId: 7, actions: ["manage_events", "manage_bookings"],
      makerspace: { id: 3, enabled_modules: ["events", "bookings"] } }}>
      <EventVenueBookingPanel makerspaceId={3} eventId={4} readOnly={false} />
    </StaffListContext.Provider>
  </QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Manage venue booking" }));
  await screen.findByText(/Booking #31 is linked/);
}

it("flags an event that moved outside its room booking and points to Bookings without changing it", async () => {
  await panel({ ...linked, event_window: { ...slot, ends_at: "2026-11-20T13:00:00Z" }, sync: "different", coverage: "not_covered" });
  expect(screen.getByText("Room booking no longer covers the event time.")).toBeInTheDocument();
  const open = screen.getByRole("link", { name: "Open the booking in Bookings" });
  expect(open.getAttribute("href")).toContain("space=6&booking=31");
  expect(mock.request.mock.calls.every(([, init]) => !init?.method || init.method === "GET")).toBe(true);
});

it("shows a cancelled event on the venue panel and keeps the booking", async () => {
  await panel({ ...linked, event_status: "cancelled" });
  expect(screen.getByText(/This event was cancelled. The room booking and its charges are kept/)).toBeInTheDocument();
  expect(screen.queryByText("Room booking no longer covers the event time.")).toBeNull();
});

it("shows nothing extra while the booking still covers the event", async () => {
  await panel(linked);
  expect(screen.queryByText(/no longer covers/)).toBeNull();
  expect(screen.queryByText(/was cancelled/)).toBeNull();
});

it("labels a calendar booking with the event only when the viewer may see it", () => {
  expect(linkedEventText({ kind: "event", title: "Robotics night", event_status: "published" })).toBe("Event: Robotics night");
  expect(linkedEventText({ kind: "event", title: "Robotics night", event_status: "cancelled" })).toBe("Event (cancelled): Robotics night");
  expect(linkedEventText({ kind: "reserved" })).toBe("Reserved");
  expect(linkedEventText(null)).toBe("");
});
