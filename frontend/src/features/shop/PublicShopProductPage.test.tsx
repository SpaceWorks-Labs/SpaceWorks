import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { PublicShopProductPage } from "./PublicShopProductPage";

const mocks = vi.hoisted(() => ({ tenant: vi.fn(), selling: true }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"),
  tenantPublicRequest: mocks.tenant }));
vi.mock("./useShopSpace", () => ({
  useShopSpace: () => ({ slug: "lab", name: "Lab", bootstrap: { charges_tracked: { shop: mocks.selling } },
    brandStyle: {}, path: (part = "") => `/m/lab${part ? `/${part}` : ""}`,
    chrome: { makerspace: { slug: "lab", name: "Lab" }, nav: [], footer: { links: [] } } }),
  useMemberSession: () => ["anonymous", vi.fn()],
}));

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: query.includes("min-width"), media: query,
    addEventListener: vi.fn(), removeEventListener: vi.fn() }));
  mocks.selling = true;
  window.localStorage.clear();
  mocks.tenant.mockImplementation((_slug: string, path: string) => Promise.resolve(path.endsWith("/shop/")
    ? { name: "Lab", currency: "inr", pay_online: false, guest_checkout: true, member_prices: false,
      policy_text: "", pickup_note: "", returns_days: 0, hold_minutes: 2880, pickup_events: [] }
    : { id: 1, slug: "pen", name: "Pen", kind: "other", description: "Catalogue description", unit: "", category: "",
      image_url: "", price_from: mocks.selling ? 10 : null, price_to: mocks.selling ? 10 : null,
      sold_out: false, members_only: false, max_per_order: null,
      variants: [{ id: 11, name: "Standard", options: {}, price: mocks.selling ? 10 : null,
        sold_out: false, stock_label: "in_stock", stock_count: null }] }));
});

afterEach(() => vi.unstubAllGlobals());

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/m/lab/shop/pen"]}>
    <Routes><Route path="/m/:slug/shop/:productSlug" element={<PublicShopProductPage />} /></Routes>
  </MemoryRouter></QueryClientProvider>);
}

it.each([true, false])("keeps catalogue details and hides sale actions with charges off (desktop=%s)", async desktop => {
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: desktop && query.includes("min-width"), media: query,
    addEventListener: vi.fn(), removeEventListener: vi.fn() }));
  mocks.selling = false;
  window.localStorage.setItem("spaceworks.shop.cart:lab", JSON.stringify([
    { variantId: 11, label: "Pen", quantity: 1, price: "10", productSlug: "pen" },
  ]));
  show();
  expect(await screen.findByText("Catalogue description")).toBeVisible();
  expect(screen.queryByRole("button", { name: "Add to basket" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /View basket/ })).not.toBeInTheDocument();
  expect(screen.queryByRole("list", { name: "Basket" })).not.toBeInTheDocument();
  if (!desktop) fireEvent.click(screen.getByRole("button", { name: "View item" }));
  expect(await screen.findByText("This shop is not taking orders right now.")).toBeVisible();
  expect(screen.queryByRole("button", { name: "Add to basket" })).not.toBeInTheDocument();
  expect(window.localStorage.getItem("spaceworks.shop.cart:lab")).not.toBeNull();
});

it("allows a purchase when charges are on without requiring an online rail", async () => {
  show();
  expect(await screen.findByRole("button", { name: "Add to basket" })).toBeEnabled();
  expect(screen.getByText(/and pay at the desk\./)).toBeVisible();
});
