import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import { StructuredApiError } from "../../lib/api";
import { EventWorkshopMachines } from "./EventWorkshopMachines";
import { StaffListContext } from "./StaffListContext";
import { machineAccessText } from "./eventEquipment/machineLinkErrors";

const route = "/admin/makerspace/3/events/4/workshop-machines";
const window = { starts_at: "2026-11-20T10:00:00Z", ends_at: "2026-11-20T12:00:00Z" };
const row = { link_id: 1, state: "linked", booking_id: 20, current_booking_id: 20, machine_name: "Laser A",
  booking_window: window, reservation_state: "confirmed", replaceable: false, history: [], warnings: [] };

function show(request: ReturnType<typeof vi.fn>, readOnly = false) {
  return render(<QueryClientProvider client={new QueryClient()}>
    <StaffListContext.Provider value={{ ownerName: "", canShare: false, actorId: 7, makerspace: { id: 3, enabled_modules: ["machines"] } }}>
      <EventWorkshopMachines makerspaceId={3} eventId={4} readOnly={readOnly} request={request as never} queryKey={["venue", 3, 4]} />
    </StaffListContext.Provider>
  </QueryClientProvider>);
}

function routes(request: ReturnType<typeof vi.fn>) {
  let linked = [row];
  request.mockImplementation(async (path: string, init?: RequestInit) => {
    if (path === `${route}/1` && init?.method === "DELETE") { linked = []; return { link_id: 1, unlinked: true, unlinked_at: "2026-11-10T00:00:00Z" }; }
    if (path === route) return { event_window: window, event_status: "published", results: linked, withheld: 0, max_links: 50 };
    return { results: [], previous: null, next: null };
  });
}

it("unlinks a workshop machine only after the confirm dialog", async () => {
  const request = vi.fn();
  routes(request);
  show(request);
  fireEvent.click(await screen.findByRole("button", { name: "Unlink machine booking #20" }));
  expect(screen.getByRole("dialog", { name: "Unlink this machine booking?" })).toHaveTextContent("charge and receipts");
  expect(request).not.toHaveBeenCalledWith(`${route}/1`, expect.anything());
  fireEvent.click(screen.getByRole("button", { name: "Unlink" }));
  await waitFor(() => expect(request).toHaveBeenCalledWith(`${route}/1`, { method: "DELETE" }));
  expect(await screen.findByText("No machine bookings are linked to this event.")).toBeInTheDocument();
});

it("offers no unlink on a read-only event", async () => {
  const request = vi.fn();
  routes(request);
  show(request, true);
  await screen.findByText("Laser A");
  expect(screen.queryByRole("button", { name: /Unlink/ })).toBeNull();
});

it("names the booker or organizer machine access refusal (decision 319)", () => {
  const error = new StructuredApiError(403, { code: "no_machine_access" });
  expect(machineAccessText(error)).toContain("booker or the event organizer");
  expect(machineAccessText(error)).toContain("Machine access");
  expect(machineAccessText(new StructuredApiError(403, { code: "machine_access_expired" }))).toContain("has ended");
  expect(machineAccessText(new Error("x"))).toBeNull();
});
