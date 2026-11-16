import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { BuyerLinks } from "./ShopBuyerLinks";
import { ShopOrders } from "./ShopOrders";
import { ShopStock } from "./ShopStock";
import { shopAccess } from "./shopAccess";

const api = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async original => ({ ...(await original<object>()), staffRequest: api.staffRequest }));

const access = shopAccess(["manage_shop"], false, { enabled_modules: ["shop"], enabled_features: [] });
function wrap(node: ReactNode, path = "/m/lab/admin/shop/orders") {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={[path]}>{node}</MemoryRouter></QueryClientProvider>);
}
const variant = (id: number, available: number, reorder: number) => ({ id, name: "Std", on_hand: available, held: 0, available, reorder_point: reorder, sku: `S${id}`, archived_at: null });

describe("shop lists (SH2)", () => {
  beforeEach(() => { api.staffRequest.mockReset(); api.staffRequest.mockImplementation(() => new Promise(() => {})); });

  it("narrows the order queue to one buyer from a cross-link and lets staff clear it", async () => {
    api.staffRequest.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    wrap(<ShopOrders makerspaceId={4} access={access} />, "/m/lab/admin/shop/orders?buyer=21");
    await waitFor(() => expect(api.staffRequest).toHaveBeenCalledWith(expect.stringMatching(/\/orders\/\?page=1&buyer=21$/)));
    expect(await screen.findByText("No orders match these filters.")).toBeInTheDocument();
  });

  it("shows only items that need reordering on request", async () => {
    api.staffRequest.mockResolvedValue({ count: 2, next: null, previous: null, results: [
      { id: 1, name: "Filament", variants: [variant(11, 2, 5)] }, { id: 2, name: "Tape", variants: [variant(12, 40, 5)] }] });
    wrap(<ShopStock makerspaceId={4} access={access} />, "/m/lab/admin/shop/stock");
    expect(await screen.findByText("Tape")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Low stock only" }));
    expect(screen.queryByText("Tape")).toBeNull();
    expect(screen.getByText("Filament")).toBeInTheDocument();
  });

  it("links an order's buyer to their member activity and their other orders", () => {
    const onOrders = vi.fn();
    wrap(<BuyerLinks name="Asha" buyerId={21} memberHref="/m/lab/admin/members?member=21" onOrders={onOrders} />);
    expect(screen.getByRole("link", { name: "Asha" })).toHaveAttribute("href", "/m/lab/admin/members?member=21");
    fireEvent.click(screen.getByRole("button", { name: "Their orders" }));
    expect(onOrders).toHaveBeenCalledWith(21);
  });

  it("keeps a guest buyer as plain text", () => {
    wrap(<BuyerLinks name="Walk-in" buyerId={null} />);
    expect(screen.getByText("Walk-in")).toBeInTheDocument();
    expect(screen.queryByRole("link")).toBeNull();
  });
});
