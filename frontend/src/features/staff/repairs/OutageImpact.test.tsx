import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { OutageImpact } from "./ServiceStateDialog";

const api = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async original => ({ ...(await original<object>()), staffRequest: api.staffRequest }));

function show(back = "") {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <OutageImpact makerspaceId={4} roomId={6} back={back} />
  </QueryClientProvider>);
}

beforeEach(() => { api.staffRequest.mockReset(); });

it("previews the bookings and visible events an outage would meet before saving", async () => {
  api.staffRequest.mockResolvedValue({ already_out_of_service: false, booking_count: 2,
    bookings: [{ id: 8, starts_at: "2026-11-20T10:00:00Z", ends_at: "2026-11-20T12:00:00Z", status: "confirmed" }],
    events: [{ event_id: 3, title: "Robot night", event_status: "published" }], other_event_bookings: 1 });
  show("2026-11-21T09:00");
  expect(await screen.findByText("2 pending or confirmed bookings fall in this time.")).toBeVisible();
  expect(screen.getByText("Robot night")).toBeVisible();
  expect(screen.getByText("1 more bookings hold the room for events you cannot see.")).toBeVisible();
  const [path] = api.staffRequest.mock.calls[0];
  expect(path).toContain("/admin/makerspaces/4/room-outages/impact?room_id=6&expected_back_at=");
});

it("says so when nothing is booked and stays silent when the preview is refused", async () => {
  api.staffRequest.mockResolvedValueOnce({ already_out_of_service: false, booking_count: 0, bookings: [], events: [], other_event_bookings: 0 });
  const { unmount } = show();
  expect(await screen.findByText("No bookings fall in this time.")).toBeVisible();
  expect(api.staffRequest.mock.calls[0][0]).toBe("/admin/makerspaces/4/room-outages/impact?room_id=6");
  unmount();
  api.staffRequest.mockRejectedValueOnce(new Error("forbidden"));
  const { container } = show();
  await vi.waitFor(() => expect(container.querySelector("[role=status]")).toBeNull());
  expect(screen.queryByLabelText("Outage impact")).toBeNull();
});
