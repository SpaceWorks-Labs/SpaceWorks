import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AllowedTabsContext } from "../areaOverview/allowedTabsContext";
import { InventoryCategoryFilter } from "./InventoryCategoryFilter";
import { InventoryItemRelated } from "./InventoryItemRelated";
import { LendingHistory } from "./InventoryLendingHistory";
import type { AdminProduct } from "./InventoryPanelShared";
import { Ledger } from "./Ledger";
import { groupLedgerRows } from "./LedgerGroups";
import type { LedgerRow } from "./LedgerParts";
import type { Category, Makerspace } from "./shared";

const api = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async original => ({ ...(await original<object>()), staffRequest: api.staffRequest }));

function wrap(node: ReactNode, tabs: string[], path = "/m/lab/admin/inventory") {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={[path]}><AllowedTabsContext.Provider value={tabs}>{node}</AllowedTabsContext.Provider></MemoryRouter>
  </QueryClientProvider>);
}
const product = { id: 5, name: "Multimeter", issued_quantity: 3, damaged_quantity: 1 } as AdminProduct;
const row = (overrides: Partial<LedgerRow>): LedgerRow => ({ source: "request", item_name: "Multimeter", container: null, units: [], target_label: null,
  holder: "Asha", quantity: 1, since: "2026-11-01T10:00:00Z", due: null, makerspace_id: 4, reference_id: 1, status: "issued",
  request_id: 31, product_id: 5, holder_id: 9, ...overrides });

describe("inventory drill-down (IN5-IN7, IN9)", () => {
  beforeEach(() => { api.staffRequest.mockReset(); api.staffRequest.mockImplementation(() => new Promise(() => {})); });

  it("links an item to its holders, requests, repairs and incidents (IN6)", async () => {
    api.staffRequest.mockResolvedValue({ count: 2, next: null, previous: null, results: [{ id: 4, title: "Probe snapped", status: "reported", occurred_at: "2026-11-02T10:00:00Z" }] });
    wrap(<InventoryItemRelated product={product} makerspaceId={4} />, ["ledger", "requests", "needsfix", "incidents"]);
    const related = screen.getByRole("region", { name: "Related" });
    expect(within(related).getByRole("link", { name: /Who has it now/ })).toHaveAttribute("href", "/m/lab/admin/ledger?q=Multimeter");
    expect(within(related).getByRole("link", { name: /Requests/ })).toHaveAttribute("href", "/m/lab/admin/requests?search=Multimeter");
    expect(within(related).queryByRole("link", { name: /To-Buy/ })).toBeNull();
    expect(await within(related).findByRole("link", { name: /Incidents/ })).toHaveAttribute("href", "/m/lab/admin/incidents?product=5");
    expect(await screen.findByRole("link", { name: /Probe snapped/ })).toHaveAttribute("href", "/m/lab/admin/incidents?incident=4");
  });

  it("pages lending history and links each lend to its request (IN5)", async () => {
    const entry = (id: number) => ({ id, request_id: 100 + id, username: `Borrower ${id}`, issued_at: "2026-11-01T10:00:00Z", quantity: 1, accepted_by: null, issued_by: null });
    api.staffRequest.mockResolvedValue({ product_id: 5, last_borrower: entry(1), recent: [entry(1), entry(2)], count: 14 });
    wrap(<LendingHistory productId={5} />, ["requests", "ledger"]);
    expect((await screen.findAllByRole("link", { name: /Borrower 2/ }))[0]).toHaveAttribute("href", "/m/lab/admin/requests?id=102");
    expect(screen.getAllByRole("link", { name: "What they have out" })[0]).toHaveAttribute("href", "/m/lab/admin/ledger?q=Borrower+1");
    expect(api.staffRequest).toHaveBeenCalledWith("/admin/inventory/5/lending-history?limit=10&offset=0");
    fireEvent.click(screen.getByRole("button", { name: /next/i }));
    await waitFor(() => expect(api.staffRequest).toHaveBeenCalledWith("/admin/inventory/5/lending-history?limit=10&offset=10"));
  });

  it("groups ledger rows by holder or item with per-group totals (IN7)", () => {
    const rows = [row({ holder: "Asha", quantity: 2 }), row({ holder: "Ravi", holder_id: 10, item_name: "Drill", product_id: 6 }), row({ holder: "Asha", quantity: 1, item_name: "Drill", product_id: 6 })];
    expect(groupLedgerRows(rows, "holder").map(group => [group.label, group.rows.length, group.quantity])).toEqual([["Asha", 2, 3], ["Ravi", 1, 1]]);
    expect(groupLedgerRows(rows, "item").map(group => [group.label, group.quantity])).toEqual([["Multimeter", 2], ["Drill", 2]]);
  });

  it("opens the loan from a ledger row, starts from ?q= and groups on request (IN7)", async () => {
    api.staffRequest.mockResolvedValue({ count: 2, results: [row({}), row({ holder: "Ravi", holder_id: 10, reference_id: 2, request_id: 32 })] });
    wrap(<Ledger makerspace={{ id: 4, slug: "lab", name: "Lab" } as Makerspace} isSuperadmin={false} />, ["requests", "inventory", "ledger"], "/m/lab/admin/ledger?q=Asha");
    expect((await screen.findAllByRole("link", { name: /Multimeter ×1/ })).length).toBe(2);
    expect(api.staffRequest).toHaveBeenCalledWith(expect.stringContaining("search=Asha"));
    expect(screen.getAllByRole("link", { name: /Multimeter ×1/ })[0]).toHaveAttribute("href", "/m/lab/admin/requests?id=31");
    expect(screen.getAllByRole("link", { name: "Item" })[0]).toHaveAttribute("href", "/m/lab/admin/inventory?item=5");
    fireEvent.change(screen.getByRole("combobox", { name: "Group" }), { target: { value: "holder" } });
    expect(screen.getByRole("region", { name: "Ravi" })).toBeInTheDocument();
  });

  it("filters the stock list by category (IN9)", () => {
    const onChange = vi.fn();
    render(<InventoryCategoryFilter categories={[{ id: 2, name: "Tools" } as Category]} value="" onChange={onChange} />);
    fireEvent.change(screen.getByRole("combobox", { name: "Category" }), { target: { value: "2" } });
    expect(onChange).toHaveBeenCalledWith("2");
  });
});
