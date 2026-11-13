import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

import { StaffListContext } from "../StaffListContext";
import { ConsumablesPanel } from "./ConsumablesPanel";
import type { ConsumableRow } from "./consumablesApi";
import type { Makerspace } from "./shared";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../../lib/api", () => ({ staffRequest: request }));
// Ordinary use is fenced to the signed-in staff session, so render as actor 1 in session "1".
vi.mock("../../../lib/api/sessionTokens", () => ({ getSessionOwner: () => "1" }));
vi.mock("../../inventory/useIntakeScope", () => ({ useIntakeScope: () => ({ context: "person", owner: "1" }) }));

const row = (patch: Partial<ConsumableRow>): ConsumableRow => ({ source: "item", id: 1, name: "Solder wire", machine_id: null, machine_name: "",
  unit: "count", remaining: "2", threshold: "5", status: "low", open_to_buy_id: null, ...patch });
const rows = [
  row({ open_to_buy_id: 44 }),
  row({ source: "machine", id: 9, name: "PLA black", machine_id: 3, machine_name: "Prusa 1", unit: "grams", remaining: "800", threshold: "200", status: "ok" }),
  row({ source: "pool", id: 4, name: "PETG white", unit: "grams", remaining: "1500", threshold: null, status: "ok" }),
];

beforeEach(() => {
  request.mockReset();
  request.mockImplementation(async (_path: string, init?: RequestInit) => init?.method === "POST" ? rows[0] : { count: 3, next: null, previous: null, results: rows });
});

function setup(path = "/m/forge/admin/consumables", canEditInventory = true) {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={[path]}><StaffListContext.Provider value={{ ownerName: "", canShare: false, actorId: 1 }}>
      <ConsumablesPanel makerspace={{ id: 7, slug: "forge", name: "Forge" } as Makerspace} canEditInventory={canEditInventory} />
    </StaffListContext.Provider></MemoryRouter>
  </QueryClientProvider>);
}

it("lists items, machine consumables and pools with their source, level and low badge", async () => {
  setup();
  expect(await screen.findByText("Solder wire")).toBeInTheDocument();
  expect(request).toHaveBeenCalledWith("/admin/makerspace/7/consumables");
  expect(screen.getByText("Item")).toBeInTheDocument();
  expect(screen.getByText("Machine")).toBeInTheDocument();
  expect(screen.getByText("Material pool")).toBeInTheDocument();
  expect(screen.getAllByText("Low")).toHaveLength(1);
  expect(screen.getByText(/Prusa 1/)).toBeInTheDocument();
  expect(screen.getByText("No reorder level", { exact: false })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Open To-Buy" })).toHaveAttribute("href", "/m/forge/admin/to-buy?status=all");
  // Only item rows are logged as used.
  expect(screen.getAllByRole("button", { name: "Log use" })).toHaveLength(1);
});

it("filters by status through the URL", async () => {
  setup("/m/forge/admin/consumables?status=low");
  await screen.findByText("Solder wire");
  expect(request).toHaveBeenCalledWith("/admin/makerspace/7/consumables?status=low");
});

it("logs a take-and-go use with quantity and note", async () => {
  setup();
  fireEvent.click(await screen.findByRole("button", { name: "Log use" }));
  const dialog = screen.getByRole("dialog");
  fireEvent.change(within(dialog).getByLabelText("How many were used"), { target: { value: "3" } });
  fireEvent.change(within(dialog).getByLabelText("Note (optional)"), { target: { value: "Workshop" } });
  fireEvent.click(within(dialog).getByRole("button", { name: "Log use" }));
  await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/makerspace/7/consumables/1/use",
    { method: "POST", body: JSON.stringify({ quantity: 3, note: "Workshop" }) }));
});

it("hides Log use from staff who cannot edit inventory", async () => {
  setup(undefined, false);
  await screen.findByText("Solder wire");
  expect(screen.queryByRole("button", { name: "Log use" })).not.toBeInTheDocument();
});
