import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, expect, it, vi } from "vitest";

import { RelatedFactsPanel } from "./RelatedFactsPanel";
import { StaffListContext } from "./StaffListContext";

const api = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", () => api);

beforeEach(() => { vi.resetAllMocks(); });

function view(kind: "event" | "booking", { tenant = 17, maker = tenant, enabled = ["events", "bookings"] }: { tenant?: number; maker?: number; enabled?: string[] } = {}) {
  return <QueryClientProvider client={new QueryClient()}>
    <StaffListContext.Provider value={{ ownerName: "Staff", canShare: false, actorId: 3,
      makerspace: { id: maker, enabled_modules: enabled } }}>
      <RelatedFactsPanel tenant={tenant} kind={kind} id={45} />
    </StaffListContext.Provider>
  </QueryClientProvider>;
}

it("shows each booking fact with its own source and the privacy-withheld booker", async () => {
  api.staffRequest.mockResolvedValue({
    subject: { kind: "booking", id: 45 },
    arrival: { source: "bookings.BookingCheckInEvent", booking_status: "confirmed", arrived_at: null, arrival_reversals: 0 },
    presence: { source: "presence.PresenceSession", sessions_overlapping: 2, distinct_people: 2, subject_person_presence: "withheld" },
  });
  render(view("booking"));
  expect(api.staffRequest).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "View related activity" }));
  expect(await screen.findByText("Source: Booking arrivals")).toBeInTheDocument();
  // Raw codes never reach staff: the status is a label, not an enum.
  expect(screen.getByText("Confirmed")).toBeInTheDocument();
  expect(screen.getByText("Source: Presence check-ins")).toBeInTheDocument();
  expect(screen.getByText("Hidden by presence privacy")).toBeInTheDocument();
  expect(screen.queryByText(/Machine sessions/)).toBeNull();
  expect(api.staffRequest).toHaveBeenCalledWith("/admin/makerspace/17/related-facts/bookings/45", expect.any(Object));
});

it("reports an unavailable view without inventing sections", async () => {
  api.staffRequest.mockRejectedValue(new Error("404"));
  render(view("event"));
  fireEvent.click(screen.getByRole("button", { name: "View related activity" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("unavailable for your access");
  expect(api.staffRequest).toHaveBeenCalledWith("/admin/makerspace/17/related-facts/events/45", expect.any(Object));
});

it.each(["event", "booking"] as const)("hides the %s panel for another tenant or with its module off", kind => {
  for (const options of [{ maker: 99 }, { enabled: [kind === "event" ? "bookings" : "events"] }]) {
    const result = render(view(kind, options));
    expect(screen.queryByRole("button", { name: "View related activity" })).toBeNull();
    result.unmount();
  }
});
