import { i18n } from "@lingui/core";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { PublicShopProductPage } from "./PublicShopProductPage";

const mocks = vi.hoisted(() => ({ tenant: vi.fn(), unavailable: false }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"),
  tenantPublicRequest: mocks.tenant }));
vi.mock("./useShopSpace", () => ({
  useShopSpace: () => ({ slug: "lab", name: "Lab", bootstrap: { charges_tracked: { shop: true } },
    brandStyle: {}, path: (part = "") => `/m/lab${part ? `/${part}` : ""}`,
    chrome: { makerspace: { slug: "lab", name: "Lab" }, nav: [], footer: { links: [] } } }),
  useMemberSession: () => ["anonymous", vi.fn()],
}));

beforeEach(() => {
  mocks.unavailable = false;
  window.localStorage.clear();
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: query.includes("min-width"), media: query,
    addEventListener: vi.fn(), removeEventListener: vi.fn() }));
  mocks.tenant.mockImplementation((_slug: string, path: string) => Promise.resolve(path.endsWith("/shop/")
    ? { name: "Lab", currency: "inr", pay_online: false, guest_checkout: true, member_prices: false,
      policy_text: "", pickup_note: "", returns_days: 0, hold_minutes: 2880, pickup_events: [] }
    : { id: 1, slug: "pen", name: "Pen", kind: "other", description: "A pen", unit: "tenant-unit", category: "",
      image_url: "", price_from: 10, price_to: 10, sold_out: false, members_only: false, max_per_order: null,
      variants: [{ id: 11, name: "Standard", options: {}, price: 10, sold_out: mocks.unavailable,
        stock_label: "in_stock", stock_count: null }] }));
});

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/m/lab/shop/pen"]}>
    <Routes><Route path="/m/:slug/shop/:productSlug" element={<PublicShopProductPage />} /></Routes>
  </MemoryRouter></QueryClientProvider>);
}

it("sends the complete unit phrase through Lingui with a named tenant value", async () => {
  const translate = vi.spyOn(i18n, "_");
  show();
  expect(await screen.findByText("per tenant-unit")).toBeVisible();
  expect(translate).toHaveBeenCalledWith(expect.objectContaining({
    message: "per {unit}", values: { unit: "tenant-unit" },
  }));
});

it("sends the unavailable-option explanation through Lingui", async () => {
  mocks.unavailable = true;
  const translate = vi.spyOn(i18n, "_");
  show();
  const action = await screen.findByRole("button", { name: "Add to basket" });
  expect(action).toBeDisabled();
  expect(action).toHaveAccessibleDescription("Choose an option that is in stock.");
  expect(translate).toHaveBeenCalledWith(expect.objectContaining({ message: "Choose an option that is in stock." }));
});
