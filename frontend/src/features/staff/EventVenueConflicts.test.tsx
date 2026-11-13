import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import { VenueConflictList } from "./EventVenueConflicts";
import { EventVenueNotices } from "./EventVenueNotices";
import { EventWorkshopMachines } from "./EventWorkshopMachines";
import { StaffListContext } from "./StaffListContext";

const window = { starts_at: "2026-11-20T10:00:00Z", ends_at: "2026-11-20T12:00:00Z" };

it("flags a room out of service and a closure on a live linked booking, with a link to Bookings", () => {
  render(<EventVenueNotices eventStatus="published" coverage="covers" reservationState="confirmed" bookingId={8} spaceId={6}
    conflicts={[{ code: "room_out_of_service", severity: "block", ...window, reason: "Flooded basement" },
      { code: "space_closed", severity: "warning", ...window }]} />);
  expect(screen.getByRole("alert")).toHaveTextContent("Room out of service during this event");
  expect(screen.getByText("Reason: Flooded basement")).toBeVisible();
  expect(screen.getByRole("status")).toHaveTextContent("Space closed during part of this time");
  expect(screen.getByRole("link", { name: "Open the booking in Bookings" })).toHaveAttribute("href", expect.stringContaining("booking=8"));
});

it("shows nothing for conflicts on a booking that no longer reserves the room", () => {
  const { container } = render(<EventVenueNotices eventStatus="published" coverage="covers" reservationState="historical"
    conflicts={[{ code: "room_out_of_service", severity: "block" }]} />);
  expect(container).toBeEmptyDOMElement();
});

it("renders a generic conflict without times or a reason", () => {
  render(<VenueConflictList conflicts={[{ code: "room_outage_warning", severity: "warning" }]} />);
  expect(screen.getByRole("status")).toHaveTextContent("Room outage reported during this event");
  expect(screen.queryByText(/Reason:/)).toBeNull();
  expect(screen.queryByText(/2026/)).toBeNull();
});

it("shows a workshop machine's repair conflict once and keeps unrelated readiness warnings", async () => {
  const request = vi.fn().mockResolvedValue({ event_window: window, event_status: "published", withheld: 0, max_links: 50, results: [{
    link_id: 1, state: "linked", booking_id: 20, current_booking_id: 20, current_status: "confirmed", machine_name: "Laser A",
    booking_window: window, reservation_state: "confirmed", replaceable: false, history: [],
    warnings: [{ code: "machine_repair", state: "blocked", detail: "Readiness says repair." },
      { code: "machine_lockout", state: "warning", detail: "Overdue safety maintenance locks this machine." }],
    conflicts: [{ code: "machine_under_repair", severity: "block" }],
  }] });
  render(<QueryClientProvider client={new QueryClient()}>
    <StaffListContext.Provider value={{ ownerName: "", canShare: false, actorId: 7, actions: [], makerspace: { id: 3, enabled_modules: ["events", "bookings", "machines"] } }}>
      <EventWorkshopMachines makerspaceId={3} eventId={4} readOnly request={request as never} queryKey={["venue", 3, 4]} />
    </StaffListContext.Provider>
  </QueryClientProvider>);
  expect(await screen.findByText("Machine under repair during this booking")).toBeVisible();
  expect(screen.queryByText("Readiness says repair.")).toBeNull();
  expect(screen.getByText("Overdue safety maintenance locks this machine.")).toBeVisible();
});
