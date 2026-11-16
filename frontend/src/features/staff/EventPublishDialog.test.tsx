import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../lib/api";
import { EventPublishDialog } from "./EventPublishDialog";

const mock = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../lib/api", async original => ({ ...await original<typeof import("../../lib/api")>(), staffRequest: mock.request }));

const panel = {
  event_id: 4, event_status: "draft", event_window: { starts_at: "2030-01-01T10:00:00Z", ends_at: "2030-01-01T12:00:00Z" },
  venue: { state: "blocked", reason: "rejected", booking_id: 9, space_name: "Hall" }, warnings: [],
  requires_override: true, can_publish: false, venue_fee: null, offers: [], can_manage_booking: true,
};

function show(error: unknown = null) {
  const onPublish = vi.fn();
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <EventPublishDialog open makerspaceId={3} eventId={4} pending={false} error={error} onCancel={vi.fn()} onPublish={onPublish} />
  </QueryClientProvider>);
  return onPublish;
}

beforeEach(() => { mock.request.mockReset(); });

it("blocks a rejected room until the organizer chooses to publish without a room", async () => {
  mock.request.mockResolvedValue(panel);
  const onPublish = show();
  expect(await screen.findByText("The booking for Hall was rejected.")).toBeInTheDocument();
  expect(mock.request).toHaveBeenCalledWith("/admin/makerspace/3/events/4/venue", expect.anything());
  const publish = screen.getByRole("button", { name: "Publish" });
  expect(publish).toBeDisabled();
  fireEvent.click(screen.getByRole("checkbox", { name: /Publish without a room/ }));
  fireEvent.click(publish);
  expect(onPublish).toHaveBeenCalledWith({ publish_without_room: true });
});

it("warns about a pending room, capacity and a venue fee without blocking", async () => {
  mock.request.mockResolvedValue({ ...panel, venue: { state: "pending", reason: "", booking_id: 9, space_name: "Hall", coverage: "covers" },
    requires_override: false, can_publish: true, venue_fee: { will_charge_on_publish: true },
    warnings: [{ code: "venue_pending" }, { code: "event_capacity_above_room", event_capacity: 40, room_capacity: 20 }] });
  const onPublish = show();
  expect(await screen.findByText(/awaits approval/)).toBeInTheDocument();
  expect(screen.getByText("The event allows 40 places but the room holds 20.")).toBeInTheDocument();
  expect(screen.getByText(/charges the configured venue fee/)).toBeInTheDocument();
  expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Publish" }));
  expect(onPublish).toHaveBeenCalledWith({});
});

it("explains a 409 venue refusal and rereads the venue", async () => {
  mock.request.mockResolvedValue(panel);
  show(new StructuredApiError(409, { code: "venue_booking_blocked", detail: "blocked" }));
  expect(await screen.findByText(/no longer usable/)).toBeInTheDocument();
  expect(mock.request.mock.calls.length).toBeGreaterThanOrEqual(1);
});
