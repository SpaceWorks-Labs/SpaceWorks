import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TenantProvider } from "../../../lib/tenant";
import { listMemberShopOrders } from "../../shop/shopApi";
import { MemberShopOrdersPage } from "./MemberShopOrdersPage";

vi.mock("../../events/ticketing/MemberOrdersPage", () => ({ useMemberSpace: () => ({ makerspaceId: 3, makerspaceSlug: "workshop", loading: false }) }));
vi.mock("../../shop/shopApi", async (original) => ({ ...await original<typeof import("../../shop/shopApi")>(), listMemberShopOrders: vi.fn() }));
vi.mock("./MemberShopOrderDetail", () => ({ MemberShopOrderDetail: ({ orderId, backHref }: { orderId: number; backHref: string }) => <a href={backHref}>Back from order {orderId}</a> }));

function show() {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={["/m/workshop/member/shop-orders"]}><TenantProvider><Routes>
      <Route path="/m/:slug/member/shop-orders/:orderId?" element={<MemberShopOrdersPage />} />
    </Routes></TenantProvider></MemoryRouter></QueryClientProvider>);
}
beforeEach(() => vi.resetAllMocks());
describe("member shop orders navigation", () => {
  it("provides tenant-aware member and shop links in the empty state", async () => {
    vi.mocked(listMemberShopOrders).mockResolvedValue({ count: 0, results: [], next: null, previous: null });
    show(); await screen.findByText("You have no shop orders yet.");
    expect(screen.getByRole("link", { name: "Member area" })).toHaveAttribute("href", "/m/workshop/member");
    for (const link of screen.getAllByRole("link", { name: "Visit the shop" })) expect(link).toHaveAttribute("href", "/m/workshop/shop");
  });
  it("shows singular and plural quantities and returns from an order to the tenant list", async () => {
    const row = (id: number, quantities: number[]) => ({ id, status: "paid", total: "10.00", currency: "INR", created_at: "2026-11-01T00:00:00Z", lines: quantities.map(quantity => ({ quantity })) });
    vi.mocked(listMemberShopOrders).mockResolvedValue({ count: 2, results: [row(11, [1]), row(12, [1, 2])], next: null, previous: null } as Awaited<ReturnType<typeof listMemberShopOrders>>);
    show(); const order = await screen.findByRole("link", { name: /Order #11/ });
    expect(order).toHaveAttribute("href", "/m/workshop/member/shop-orders/11");
    expect(order).toHaveTextContent("1 item"); expect(screen.getByRole("link", { name: /Order #12/ })).toHaveTextContent("3 items");
    fireEvent.click(order); expect(await screen.findByRole("link", { name: "Back from order 11" })).toHaveAttribute("href", "/m/workshop/member/shop-orders");
  });
});
