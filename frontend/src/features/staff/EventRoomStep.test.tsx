import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { EventRoomStep, emptyRoomChoice, roomStepPayload, type RoomChoice } from "./EventRoomStep";
import { StaffListContext } from "./StaffListContext";

const mock = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../lib/api", async original => ({ ...await original<typeof import("../../lib/api")>(), staffRequest: mock.request }));

const rooms = { count: 1, next: null, previous: null, results: [
  { id: 6, makerspace_id: 3, name: "Hall", kind: "meeting", is_active: true, capacity: 20, approval_mode: "approve", machine: null },
] };

function Harness({ onChoice }: { onChoice: (choice: RoomChoice) => void }) {
  const [value, setValue] = useState(emptyRoomChoice);
  return <EventRoomStep makerspaceId={3} start="2030-01-01T10:00" end="2030-01-01T12:00" capacity={40} value={value}
    onChange={next => { setValue(next); onChoice(next); }} />;
}

function show(actions: string[]) {
  const onChoice = vi.fn();
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <StaffListContext.Provider value={{ ownerName: "", canShare: false, actions }}><Harness onChoice={onChoice} /></StaffListContext.Provider>
  </QueryClientProvider>);
  return onChoice;
}

const choices = { results: [{ id: 6, name: "Hall", capacity: 20, needs_approval: true, status: "approval_required" }] };
let spacesDenied = false;

beforeEach(() => {
  spacesDenied = false;
  mock.request.mockReset();
  mock.request.mockImplementation(async (path: string) => {
    if (path.startsWith("/admin/makerspaces/3/spaces/")) {
      if (spacesDenied) throw new Error("Not found.");
      return rooms;
    }
    if (path === "/admin/makerspace/3/event-room-choices") return choices;
    if (path.includes("/bookings/availability/")) return { space_id: 6, timezone: "UTC", range_starts_at: "", range_ends_at: "", opening_intervals: [], busy: [], pending: [], requested: { within_rules: true, rule_detail: "", conflict: false, holds_room_on_create: false } };
    throw new Error(`unexpected ${path}`);
  });
});

describe("room step payload", () => {
  it("builds only complete room steps", () => {
    expect(roomStepPayload(emptyRoomChoice)).toBeNull();
    expect(roomStepPayload({ ...emptyRoomChoice, mode: "house", space_id: 6, note: " Doors at 9 " })).toEqual({ mode: "house", space_id: 6, note: "Doors at 9" });
    expect(roomStepPayload({ ...emptyRoomChoice, mode: "book", space_id: 6, member_id: 8 })).toBeNull();
    expect(roomStepPayload({ ...emptyRoomChoice, mode: "book", space_id: 6, member_id: 8, price_confirmation: "a".repeat(64) }))
      .toEqual({ mode: "book", space_id: 6, member_id: 8, price_confirmation: "a".repeat(64) });
    expect(roomStepPayload({ ...emptyRoomChoice, mode: "link", booking_id: 12 })).toEqual({ mode: "link", booking_id: 12 });
  });
});

describe("room step", () => {
  it("lets a booking manager house-book a room and warns about capacity and approval", async () => {
    const onChoice = show(["manage_events", "manage_bookings"]);
    fireEvent.click(screen.getByRole("radio", { name: /House booking/ }));
    fireEvent.change(await screen.findByRole("combobox", { name: "Room" }), { target: { value: "6" } });
    expect(onChoice).toHaveBeenLastCalledWith(expect.objectContaining({ mode: "house", space_id: 6 }));
    expect(screen.getByText(/allows 40 places but Hall holds 20/)).toBeInTheDocument();
    expect(await screen.findByLabelText("Room availability")).toBeInTheDocument();
  });

  it("offers an event manager without booking authority only a room request, from the room choices", async () => {
    spacesDenied = true;
    const onChoice = show(["manage_events"]);
    expect(screen.getByRole("radio", { name: /Request a room/ })).toBeInTheDocument();
    expect(screen.queryByRole("radio", { name: /Link an existing booking/ })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("radio", { name: /Request a room/ }));
    fireEvent.change(await screen.findByRole("combobox", { name: "Room" }), { target: { value: "6" } });
    expect(onChoice).toHaveBeenLastCalledWith(expect.objectContaining({ mode: "request", space_id: 6 }));
    expect(screen.getByText(/needs approval/, { selector: "p" })).toBeInTheDocument();
    expect(screen.getByText(/allows 40 places but Hall holds 20/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Room availability")).not.toBeInTheDocument();
    expect(mock.request).toHaveBeenCalledWith("/admin/makerspace/3/event-room-choices", expect.anything());
  });

  it("keeps a booking manager's room request on the full spaces list", async () => {
    show(["manage_events", "manage_bookings"]);
    fireEvent.click(screen.getByRole("radio", { name: /Request a room/ }));
    expect(await screen.findByRole("combobox", { name: "Room" })).toBeInTheDocument();
    expect(mock.request).not.toHaveBeenCalledWith("/admin/makerspace/3/event-room-choices", expect.anything());
  });
});
