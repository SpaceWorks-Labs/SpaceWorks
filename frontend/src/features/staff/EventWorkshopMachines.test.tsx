import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import { StructuredApiError } from "../../lib/api";
import { EventWorkshopMachines } from "./EventWorkshopMachines";
import { StaffListContext } from "./StaffListContext";

const route = "/admin/makerspace/3/events/4/workshop-machines";
const window = { starts_at: "2026-11-20T10:00:00Z", ends_at: "2026-11-20T12:00:00Z" };
const page = (results: unknown[]) => ({ results, previous: null, next: null });
const linkedRow = {
  link_id: 1, state: "linked", booking_id: 20, current_booking_id: 20, current_status: "confirmed",
  space_name: "Laser A time", machine_name: "Laser A", booking_window: window, reservation_state: "confirmed",
  replaceable: false, history: [], warnings: [{ code: "machine_lockout", state: "warning", detail: "Overdue safety maintenance locks this machine." }],
};
const listing = (results: unknown[], withheld = 0) => ({ event_window: window, event_status: "draft", results, withheld, max_links: 50 });

function show(request: ReturnType<typeof vi.fn>, modules = ["events", "bookings", "machines"]) {
  return render(<QueryClientProvider client={new QueryClient()}>
    <StaffListContext.Provider value={{ ownerName: "", canShare: false, actorId: 7, actions: [], makerspace: { id: 3, enabled_modules: modules } }}>
      <EventWorkshopMachines makerspaceId={3} eventId={4} readOnly={false} request={request as never} queryKey={["venue", 3, 4]} />
    </StaffListContext.Provider>
  </QueryClientProvider>);
}

function routes(request: ReturnType<typeof vi.fn>, onPost: (body: Record<string, unknown>) => unknown) {
  request.mockImplementation(async (path: string, init?: RequestInit) => {
    if (path === route && init?.method === "POST") return onPost(JSON.parse(String(init.body)));
    if (path === route) return listing([linkedRow], 1);
    if (path === "/admin/makerspaces/3/spaces/?page=1") return page([
      { id: 6, makerspace_id: 3, name: "Meeting room", kind: "meeting", machine: null, is_active: true, staff_permissions: ["manage_reservations"] },
      { id: 9, makerspace_id: 3, name: "CNC A time", kind: "machine", machine: 12, is_active: true, staff_permissions: ["manage_reservations"] },
    ]);
    if (path === "/admin/spaces/9/bookings/?page=1&ordering=starts_at") return page([
      { id: 21, space_id: 9, status: "pending", name: "Booker", ...window },
    ]);
    throw new Error(`Unexpected route ${path}`);
  });
}

it("lists linked machines with their status, advisory warnings and withheld links", async () => {
  const request = vi.fn();
  routes(request, () => ({}));
  show(request);
  expect(await screen.findByText("Laser A")).toBeTruthy();
  expect(screen.getByText(/Confirmed/)).toBeTruthy();
  expect(screen.getByText("Overdue safety maintenance locks this machine.")).toBeTruthy();
  expect(screen.getByText(/Other linked machine bookings: 1/)).toBeTruthy();
});

it("offers only machine resources and links the chosen booking", async () => {
  const request = vi.fn();
  const posted: Record<string, unknown>[] = [];
  routes(request, body => { posted.push(body); return { ...linkedRow, link_id: 2 }; });
  show(request);
  const machine = await screen.findByRole("combobox", { name: "Machine" });
  await screen.findByRole("option", { name: "CNC A time" });
  expect(screen.queryByRole("option", { name: "Meeting room" })).toBeNull();
  fireEvent.change(machine, { target: { value: "9" } });
  await screen.findByRole("option", { name: /#21/ });
  fireEvent.change(screen.getByRole("combobox", { name: "Booking" }), { target: { value: "21" } });
  fireEvent.click(screen.getByRole("button", { name: "Link machine booking" }));
  await waitFor(() => expect(posted).toEqual([{ booking_id: 21 }]));
});

it("asks for a certification override reason after a certification refusal", async () => {
  const request = vi.fn();
  const posted: Record<string, unknown>[] = [];
  routes(request, body => {
    posted.push(body);
    if (posted.length === 1) throw new StructuredApiError(403, { code: "certification_required", certifications: ["Laser induction"] });
    return { ...linkedRow, link_id: 2 };
  });
  show(request);
  await screen.findByRole("option", { name: "CNC A time" });
  fireEvent.change(screen.getByRole("combobox", { name: "Machine" }), { target: { value: "9" } });
  await screen.findByRole("option", { name: /#21/ });
  fireEvent.change(screen.getByRole("combobox", { name: "Booking" }), { target: { value: "21" } });
  fireEvent.click(screen.getByRole("button", { name: "Link machine booking" }));
  const reason = await screen.findByRole("textbox", { name: "Certification override reason" });
  fireEvent.change(reason, { target: { value: "Supervised session" } });
  fireEvent.click(screen.getByRole("button", { name: "Link machine booking" }));
  await waitFor(() => expect(posted[1]).toEqual({ booking_id: 21, certification_override_reason: "Supervised session" }));
});

it("renders nothing while the machines module is off", () => {
  const request = vi.fn();
  const { container } = show(request, ["events", "bookings"]);
  expect(container.textContent).toBe("");
  expect(request).not.toHaveBeenCalled();
});
