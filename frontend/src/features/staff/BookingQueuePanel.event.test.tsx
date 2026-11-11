import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import { BookingQueuePanel } from "./BookingQueuePanel";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", async original => ({ ...(await original<typeof import("../../lib/api")>()), staffRequest }));

it("labels a queued booking with the event it holds the room for, and house/organization bookings", async () => {
  staffRequest.mockResolvedValue({ count: 2, next: null, previous: null, results: [
    { id: 41, space_id: 4, space_name: "Hall", name: "Ada", email: "", phone: "", status: "pending", custom_answers: null, payment: null,
      starts_at: "2030-01-01T10:00:00Z", ends_at: "2030-01-01T12:00:00Z", linked_event: { kind: "event", event_id: 9, title: "Robot night", event_status: "draft" },
      organization_name: "Robotics club" },
    { id: 42, space_id: 4, space_name: "Hall", name: "Space", email: "", phone: "", status: "confirmed", custom_answers: null, payment: null,
      starts_at: "2030-01-02T10:00:00Z", ends_at: "2030-01-02T12:00:00Z", is_house: true },
  ] });
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <BookingQueuePanel makerspaceId={7} status="all" onStatus={vi.fn()} onOpenBooking={vi.fn()} /></QueryClientProvider>);
  expect(await screen.findByText("Event: Robot night")).toBeInTheDocument();
  expect(screen.getByText("For organization: Robotics club")).toBeInTheDocument();
  expect(screen.getByText("House booking (no member, no charge)")).toBeInTheDocument();
});
