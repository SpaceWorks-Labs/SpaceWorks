import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../../lib/api";
import { TenantProvider } from "../../../lib/tenant";
import { MemberSeriesPassPage } from "./MemberSeriesPassPage";

const mocks = vi.hoisted(() => ({ request: vi.fn(), assign: vi.fn(), refetchSpace: vi.fn(), spaceError: null as Error | null }));
vi.mock("../../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api"),
  memberRequest: mocks.request, getAccessToken: () => "session" }));
vi.mock("../../inventory/usePublicInventory", () => ({
  // Like the real hook, a missing slug (central portal, no space) resolves no space.
  // A failed bootstrap (spaceError) resolves no space either, and carries the error and its refetch.
  useTenantBootstrap: (slug: string) => ({ data: slug && !mocks.spaceError ? { makerspace: { id: 7 } } : undefined, isLoading: false,
    error: mocks.spaceError, refetch: mocks.refetchSpace }) }));
vi.mock("../../members/MemberAuthPanel", () => ({ MemberAuthPanel: () => <p>Sign in to buy a pass</p> }));

const passes = [
  { id: 4, name: "Season pass", amount: "40.00", capacity: 20, occurrence_refund_amount: "5.00", sales_end_at: null, is_active: true },
  { id: 5, name: "Old pass", amount: "30.00", capacity: null, occurrence_refund_amount: "0", sales_end_at: null, is_active: false },
];

function show(path = "/m/lab/member/series/12/passes") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><TenantProvider><Routes>
    <Route path="/m/:slug/member/series/:seriesId/passes" element={<MemberSeriesPassPage />} />
    <Route path="/member/series/:seriesId/passes" element={<MemberSeriesPassPage />} />
    <Route path="/m/:slug/member/orders/:orderId" element={<p>Order page</p>} />
  </Routes></TenantProvider></MemoryRouter></QueryClientProvider>);
}

const original = window.location;
beforeEach(() => {
  vi.clearAllMocks();
  mocks.spaceError = null;
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

  // Decision 598 follow-up: the central portal has no selected space, so it says where passes are sold.
  it("on the central portal with no space says where passes are sold and requests nothing", async () => {
    show("/member/series/12/passes");
    expect(await screen.findByText("Buy series passes from a makerspace's events page.")).toHaveAttribute("role", "alert");
    expect(screen.queryByRole("button", { name: "Buy this pass" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
    expect(mocks.request).not.toHaveBeenCalled();
  });

  // R9 review note C: a scoped route whose space failed to load shows its error; Retry only for an outage.
  it("offers Retry for a space bootstrap outage, and Retry refetches the space", async () => {
    mocks.spaceError = new StructuredApiError(503, { code: "service_unavailable", detail: "The space is down." });
    show();
    expect(await screen.findByText("The space is down.")).toBeVisible();
    expect(screen.queryByText("Buy series passes from a makerspace's events page.")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(mocks.refetchSpace).toHaveBeenCalledTimes(1);
    expect(mocks.request).not.toHaveBeenCalled();
  });

  it("explains a refused space bootstrap (404) with no Retry", async () => {
    mocks.spaceError = new StructuredApiError(404, { code: "not_found", detail: "No such makerspace." });
    show();
    expect(await screen.findByText("No such makerspace.")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
    expect(screen.queryByText("Buy series passes from a makerspace's events page.")).toBeNull();
    expect(mocks.request).not.toHaveBeenCalled();
  });

  it("asks a visitor to sign in", async () => {
    mocks.request.mockRejectedValue(new StructuredApiError(401, { detail: "Sign in." }));
    show();
    expect(await screen.findByText("Sign in to buy a pass")).toBeVisible();
  });
});
