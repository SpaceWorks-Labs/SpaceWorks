import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { MyBookings, type MemberBooking } from "./MyBookings";

const { memberRequest, getAccessToken } = vi.hoisted(() => ({ memberRequest: vi.fn(), getAccessToken: vi.fn((): string | null => null) }));
vi.mock("../../lib/api", () => ({ memberRequest, getAccessToken }));

const booking: MemberBooking = {
  public_token: "room-token", space_name: "Hall", timezone: "UTC",
  starts_at: "2030-01-15T10:00:00Z", ends_at: "2030-01-15T11:00:00Z",
  status: "confirmed", cancellation_cutoff_at: "2030-01-14T10:00:00Z", can_cancel: true,
  hosts_event: { kind: "event", title: "Robot night" },
};

function show() {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>
    <MyBookings slug="lab" /></QueryClientProvider>);
}

beforeEach(() => { memberRequest.mockReset(); });

it("tells the booker the room hosts an event and confirms cancelling it explicitly", async () => {
  memberRequest.mockImplementation((_path: string, options?: { method?: string }) => options?.method === "POST"
    ? Promise.resolve({ ...booking, status: "cancelled", can_cancel: false, hosts_event: null })
    : Promise.resolve({ count: 1, next: null, previous: null, results: [booking] }));
  show();
  expect(await screen.findByText("This room is held for the event “Robot night”.")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Booking actions" }));
  fireEvent.click(screen.getByRole("menuitem", { name: "Cancel booking" }));
  expect(screen.getByRole("alert")).toHaveTextContent(/Cancelling removes the event's room/);
  fireEvent.click(screen.getByRole("button", { name: "Cancel the event's room" }));
  await waitFor(() => expect(memberRequest).toHaveBeenCalledWith("/public/lab/my-bookings/room-token/cancel/",
    { method: "POST", body: JSON.stringify({ confirm_event_room: true }) }));
});

it("asks again when the server says the room started hosting an event", async () => {
  const plain = { ...booking, hosts_event: null };
  memberRequest.mockImplementation((_path: string, options?: { method?: string; body?: string }) => options?.method === "POST"
    ? options.body === "{}" ? Promise.reject(Object.assign(new Error("held"), { code: "booking_hosts_event", body: { event: { kind: "reserved" } } }))
      : Promise.resolve({ ...plain, status: "cancelled", can_cancel: false })
    : Promise.resolve({ count: 1, next: null, previous: null, results: [plain] }));
  show();
  await screen.findByText("Hall");
  fireEvent.click(screen.getByRole("button", { name: "Booking actions" }));
  fireEvent.click(screen.getByRole("menuitem", { name: "Cancel booking" }));
  fireEvent.click(screen.getByRole("button", { name: "Confirm cancellation" }));
  fireEvent.click(await screen.findByRole("button", { name: "Cancel the event's room" }));
  await waitFor(() => expect(memberRequest).toHaveBeenCalledWith("/public/lab/my-bookings/room-token/cancel/",
    { method: "POST", body: JSON.stringify({ confirm_event_room: true }) }));
});
