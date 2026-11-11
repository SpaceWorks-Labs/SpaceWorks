import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

import { StaffListContext } from "../StaffListContext";
import { ConsumablesPanel } from "./ConsumablesPanel";
import type { Makerspace } from "./shared";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../../lib/api", () => ({ staffRequest: request }));
vi.mock("../../../lib/api/sessionTokens", () => ({ getSessionOwner: () => "1" }));
vi.mock("../../inventory/useIntakeScope", () => ({ useIntakeScope: () => ({ context: "person", owner: "1" }) }));

const consumable = { source: "item", id: 1, name: "Solder wire", machine_id: null, machine_name: "", unit: "count",
  remaining: "1", threshold: "2", status: "low", open_to_buy_id: null };
const shortage = (patch: object) => ({ subject_kind: "event", subject_id: 5, subject_title: "Soldering night",
  starts_at: "2026-11-20T18:00:00Z", product_id: 1, product_name: "Solder wire", remaining_planned: 3,
  available_quantity: 1, shortage_quantity: 2, replenishment_quantity: 10, ...patch });

function setup(modules: string[], planned: unknown) {
  request.mockImplementation(async (path?: string) => {
    if (path?.endsWith("/planned-shortages")) {
      if (planned instanceof Error) throw planned;
      return planned;
    }
    return { count: 1, next: null, previous: null, results: [consumable] };
  });
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={["/m/forge/admin/consumables"]}><StaffListContext.Provider value={{ ownerName: "", canShare: false, actorId: 1 }}>
      <ConsumablesPanel makerspace={{ id: 7, slug: "forge", name: "Forge", enabled_modules: modules } as Makerspace} />
    </StaffListContext.Provider></MemoryRouter>
  </QueryClientProvider>);
}

beforeEach(() => { request.mockReset(); });

it("lists upcoming event and booking shortages with links to each activity (C25)", async () => {
  setup(["events", "bookings"], [shortage({}), shortage({ subject_kind: "booking", subject_id: 9, subject_title: "Room A",
    shortage_quantity: 0, replenishment_quantity: 4 })]);
  expect(await screen.findByRole("link", { name: "Soldering night" })).toHaveAttribute("href", "/m/forge/admin/events?event=5");
  expect(screen.getByRole("link", { name: "Booking: Room A" })).toHaveAttribute("href", "/m/forge/admin/bookings?booking=9");
  expect(screen.getByText(/Short by 2 \(needs 3, 1 in stock\)/)).toBeInTheDocument();
  expect(screen.getByText(/Suggested reorder: 4/)).toBeInTheDocument();
  expect(request).toHaveBeenCalledWith("/admin/makerspace/7/consumables/planned-shortages");
});

it("shows an empty state", async () => {
  setup(["events"], []);
  expect(await screen.findByText(/Nothing planned is short/)).toBeInTheDocument();
});

it("shows an error message when the shortages cannot load", async () => {
  setup(["bookings"], new Error("boom"));
  expect(await screen.findByText(/could not be loaded/)).toBeInTheDocument();
});

it("is not requested while events and bookings are both off", async () => {
  setup([], []);
  await screen.findByText("Solder wire");
  expect(screen.queryByText("Needed for upcoming activities")).toBeNull();
  expect(request).not.toHaveBeenCalledWith("/admin/makerspace/7/consumables/planned-shortages");
});
