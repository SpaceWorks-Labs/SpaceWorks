import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { EventVenueOffersDialog } from "./EventVenueOffersDialog";
import { EventVenueSummary } from "./EventVenueSummary";
import type { VenueOffer } from "./eventVenueApi";

const mock = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../lib/api", async original => ({ ...await original<typeof import("../../lib/api")>(), staffRequest: mock.request }));

const wrap = (node: React.ReactNode) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{node}</QueryClientProvider>);

beforeEach(() => { mock.request.mockReset(); });

it("offers to cancel or move the room but never acts until staff press the button", async () => {
  mock.request.mockResolvedValue({});
  const window = { starts_at: "2030-01-02T10:00:00Z", ends_at: "2030-01-02T12:00:00Z" };
  const offers: VenueOffer[] = [
    { action: "move_booking", booking_id: 8, route: "admin-booking-time-edit", allowed: true, proposed_window: window },
    { action: "change_venue_fee", booking_id: null, route: "admin-event-venue-fee", allowed: true, fee_status: "configured" },
  ];
  const onReviewFee = vi.fn();
  wrap(<EventVenueOffersDialog makerspaceId={3} eventId={4} offers={offers} onClose={vi.fn()} onReviewFee={onReviewFee} />);
  expect(screen.getByText(/Nothing was changed on the room booking/)).toBeInTheDocument();
  expect(mock.request).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Move the room booking" }));
  await waitFor(() => expect(mock.request).toHaveBeenCalledWith("/admin/bookings/8/time/", { method: "POST", body: JSON.stringify(window) }));
  expect(await screen.findByText("Room booking moved.")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Review venue fee" }));
  expect(onReviewFee).toHaveBeenCalled();
});

it("tells staff without room authority whom to ask", () => {
  wrap(<EventVenueOffersDialog makerspaceId={3} eventId={4} onClose={vi.fn()}
    offers={[{ action: "cancel_booking", booking_id: 8, route: "admin-booking-cancel", allowed: false }]} />);
  expect(screen.queryByRole("button", { name: "Cancel the room booking" })).not.toBeInTheDocument();
  expect(screen.getByText("Ask a Booking Manager to change the room booking.")).toBeInTheDocument();
});

it("shows co-organizers a read-only venue with no booking controls", async () => {
  mock.request.mockResolvedValue({
    event_id: 4, event_status: "draft", event_window: { starts_at: "2030-01-01T10:00:00Z", ends_at: "2030-01-01T12:00:00Z" },
    venue: { state: "blocked", reason: "cancelled", booking_id: 9, space_name: "Hall" }, warnings: [],
    requires_override: true, can_publish: false, venue_fee: null, offers: [], can_manage_booking: false,
  });
  wrap(<EventVenueSummary makerspaceId={3} eventId={4} />);
  expect(await screen.findByText("The booking for Hall was cancelled.")).toBeInTheDocument();
  expect(screen.getByText("Room needs attention")).toBeInTheDocument();
  expect(screen.getByText(/Ask a Booking Manager to replace the room booking/)).toBeInTheDocument();
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
});
