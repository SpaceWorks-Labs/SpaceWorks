import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../../lib/api";
import { TenantProvider } from "../../../lib/tenant";
import { MemberSeriesPassPage } from "./MemberSeriesPassPage";

const mocks = vi.hoisted(() => ({ request: vi.fn(), assign: vi.fn() }));
vi.mock("../../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api"),
  memberRequest: mocks.request, getAccessToken: () => "session" }));
vi.mock("../../inventory/usePublicInventory", () => ({
  useTenantBootstrap: () => ({ data: { makerspace: { id: 7 } }, isLoading: false }) }));
vi.mock("../../members/MemberAuthPanel", () => ({ MemberAuthPanel: () => <p>Sign in to buy a pass</p> }));

const passes = [
  { id: 4, name: "Season pass", amount: "40.00", capacity: 20, occurrence_refund_amount: "5.00", sales_end_at: null, is_active: true },
  { id: 5, name: "Old pass", amount: "30.00", capacity: null, occurrence_refund_amount: "0", sales_end_at: null, is_active: false },
];

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/m/lab/member/series/12/passes"]}><TenantProvider><Routes>
    <Route path="/m/:slug/member/series/:seriesId/passes" element={<MemberSeriesPassPage />} />
    <Route path="/m/:slug/member/orders/:orderId" element={<p>Order page</p>} />
  </Routes></TenantProvider></MemoryRouter></QueryClientProvider>);
}

const original = window.location;
beforeEach(() => {
  vi.clearAllMocks();
  Object.defineProperty(window, "location", { configurable: true, value: { ...original, assign: mocks.assign } });
});
afterEach(() => { Object.defineProperty(window, "location", { configurable: true, value: original }); });

describe("series pass page", () => {
  it("lists active passes and sends the buyer to checkout", async () => {
    mocks.request.mockImplementation((_path: string, init?: RequestInit) => Promise.resolve(init?.method === "POST"
      ? { order: { id: 44 }, checkout_url: "https://pay.example.com/c/9" } : passes));
    show();
    expect(await screen.findByText("Season pass")).toBeVisible();
    expect(screen.queryByText("Old pass")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Buy this pass" }));
    await waitFor(() => expect(mocks.request).toHaveBeenCalledWith("/member/makerspaces/7/event-series/12/passes/",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ pass_type_id: 4 }) })));
    await waitFor(() => expect(mocks.assign).toHaveBeenCalledWith("https://pay.example.com/c/9"));
  });

  it("opens the order when there is nothing to pay online", async () => {
    mocks.request.mockImplementation((_path: string, init?: RequestInit) => Promise.resolve(init?.method === "POST"
      ? { order: { id: 44 }, checkout_url: "javascript:alert(1)" } : passes));
    show();
    fireEvent.click(await screen.findByRole("button", { name: "Buy this pass" }));
    expect(await screen.findByText("Order page")).toBeVisible();
    expect(mocks.assign).not.toHaveBeenCalled();
  });

  it("says passes are not on sale while the switch is off", async () => {
    mocks.request.mockRejectedValue(new StructuredApiError(400, { detail: "This events feature is disabled." }));
    show();
    expect(await screen.findByText("Passes for this series are not on sale.")).toBeVisible();
  });

  it("asks a visitor to sign in", async () => {
    mocks.request.mockRejectedValue(new StructuredApiError(401, { detail: "Sign in." }));
    show();
    expect(await screen.findByText("Sign in to buy a pass")).toBeVisible();
  });
});
