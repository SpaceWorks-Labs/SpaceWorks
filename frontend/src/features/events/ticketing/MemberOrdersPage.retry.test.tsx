import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../../lib/api";
import { TenantProvider } from "../../../lib/tenant";
import { MemberShopOrdersPage } from "../../members/shopOrders/MemberShopOrdersPage";
import { MemberOrdersPage } from "./MemberOrdersPage";

const mocks = vi.hoisted(() => ({ request: vi.fn(), refetchSpace: vi.fn(),
  space: { id: 7 as number | undefined, error: null as Error | null } }));
vi.mock("../../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api"),
  memberRequest: mocks.request }));
vi.mock("../../inventory/usePublicInventory", () => ({
  useTenantBootstrap: () => ({ data: mocks.space.id ? { makerspace: { id: mocks.space.id } } : undefined, isLoading: false,
    error: mocks.space.error, refetch: mocks.refetchSpace }) }));
vi.mock("../../members/MemberAuthPanel", () => ({ MemberAuthPanel: () => <p>Sign in to see your orders</p> }));

const NOTICE = "Open your orders from a makerspace's member area.";
function show(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><TenantProvider><Routes>
    {["/m/:slug/member/orders", "/m/:slug/member/orders/:orderId", "/member/orders", "/member/orders/:orderId"]
      .map(pattern => <Route key={pattern} path={pattern} element={<MemberOrdersPage />} />)}
    {["/member/shop-orders", "/m/:slug/member/shop-orders"].map(pattern => <Route key={pattern} path={pattern} element={<MemberShopOrdersPage />} />)}
  </Routes></TenantProvider></MemoryRouter></QueryClientProvider>);
}

beforeEach(() => { vi.clearAllMocks(); mocks.space.id = 7; mocks.space.error = null; });

// Decision 588: Retry only where a retry can succeed (5xx, 429, no response); a refusal gets its way out instead.
describe("my orders: outage versus refusal", () => {
  it("offers Retry for an outage and fetches again when it is pressed", async () => {
    mocks.request.mockRejectedValue(new StructuredApiError(503, { code: "service_unavailable", detail: "Orders are down." }));
    show("/m/lab/member/orders");
    expect(await screen.findByText("Orders are down.")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(mocks.request).toHaveBeenCalledTimes(2));
  });

  it.each([
    [403, "permission_denied", "You can't see these orders."],
    [404, "module_disabled", "Events are switched off here."],
  ])("explains a %s %s refusal with the Member area way out and no Retry", async (status, code, detail) => {
    mocks.request.mockRejectedValue(new StructuredApiError(status, { code, detail }));
    show("/m/lab/member/orders");
    expect(await screen.findByText(detail)).toBeVisible();
    expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
    expect(screen.getByRole("link", { name: "Member area" })).toHaveAttribute("href", "/m/lab/member");
    expect(mocks.request).toHaveBeenCalledTimes(1);
  });

  it("keeps Retry on an order detail outage and drops it for a missing order", async () => {
    let detail: StructuredApiError = new StructuredApiError(500, { detail: "Server error." });
    mocks.request.mockImplementation(async (path: string) => {
      if (path.endsWith("/orders/")) return { results: [] };
      throw detail;
    });
    show("/m/lab/member/orders/44");
    expect(await screen.findByRole("button", { name: "Retry" })).toBeVisible();
    detail = new StructuredApiError(404, { code: "not_found", detail: "No such order." });
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("No such order.")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
    expect(screen.getByRole("link", { name: "My orders" })).toHaveAttribute("href", "/m/lab/member/orders");
  });
});

// R8 review finding 2: a scoped route whose space bootstrap failed is an error state, never the contextless notice.
describe("my orders when the scoped space fails to load", () => {
  it.each(["/m/lab/member/orders", "/m/lab/member/orders/44", "/m/lab/member/shop-orders"])("%s: a bootstrap outage offers Retry and no notice", async path => {
    mocks.space.id = undefined;
    mocks.space.error = new StructuredApiError(503, { code: "service_unavailable", detail: "The space is down." });
    show(path);
    expect(await screen.findByText("The space is down.")).toBeVisible();
    expect(screen.queryByText(NOTICE)).toBeNull();
    expect(screen.getByRole("link", { name: "Member area" })).toHaveAttribute("href", "/m/lab/member");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(mocks.refetchSpace).toHaveBeenCalledTimes(1);
    expect(mocks.request).not.toHaveBeenCalled();
  });

  it("a refused bootstrap (module off) keeps its explanation and Member area, with no Retry and no notice", async () => {
    mocks.space.id = undefined;
    mocks.space.error = new StructuredApiError(404, { code: "module_disabled", detail: "Events are switched off here." });
    show("/m/lab/member/orders");
    expect(await screen.findByText("Events are switched off here.")).toBeVisible();
    expect(screen.queryByText(NOTICE)).toBeNull();
    expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
    expect(screen.getByRole("link", { name: "Member area" })).toHaveAttribute("href", "/m/lab/member");
  });

  // R9 review note D: cached bootstrap data plus a failed background refetch keeps the working page.
  it("keeps the orders list when the space is cached and only a background refetch failed", async () => {
    mocks.space.error = new StructuredApiError(503, { code: "service_unavailable", detail: "The space is down." });
    mocks.request.mockResolvedValue({ results: [] });
    show("/m/lab/member/orders");
    expect(await screen.findByText("You have no ticket orders yet.")).toBeVisible();
    expect(screen.queryByText("The space is down.")).toBeNull();
    expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
  });
});

describe("my orders with no selected space (central portal)", () => {
  it.each(["/member/orders", "/member/orders/44", "/member/shop-orders"])("%s says where orders live instead of a false empty state", async path => {
    mocks.space.id = undefined;
    show(path);
    expect(await screen.findByText(NOTICE)).toHaveAttribute("role", "alert");
    expect(screen.queryByText("You have no ticket orders yet.")).toBeNull();
    expect(screen.queryByText("You have no shop orders yet.")).toBeNull();
    expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
    expect(mocks.request).not.toHaveBeenCalled();
  });
});
