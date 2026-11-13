import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PublicShopPage } from "./PublicShopPage";
import type { ShopPublicProduct, ShopSummary } from "./shopApi";

const mocks = vi.hoisted(() => ({ tenant: vi.fn(), member: vi.fn(), selling: undefined as boolean | undefined }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"),
  tenantPublicRequest: mocks.tenant, tenantMemberRequest: mocks.member }));
vi.mock("./useShopSpace", () => ({
  useShopSpace: () => ({ slug: "lab", name: "Lab", bootstrap: mocks.selling === undefined ? undefined : { charges_tracked: { shop: mocks.selling } },
    brandStyle: {}, path: (part = "") => `/m/lab${part ? `/${part}` : ""}`,
    chrome: { makerspace: { slug: "lab", name: "Lab" }, nav: [], footer: { links: [] } } }),
  useMemberSession: () => ["anonymous", vi.fn()],
}));

const shop: ShopSummary = { name: "Lab", currency: "inr", pay_online: false, guest_checkout: true, member_prices: false,
  policy_text: "No refunds on cut material.", pickup_note: "Collect at the front desk.", returns_days: 7, hold_minutes: 2880, pickup_events: [] };
const variant = (id: number, extra: Partial<ShopPublicProduct["variants"][number]>) => ({ id, name: "", options: {}, price: 10, sold_out: false,
  stock_label: "in_stock" as const, stock_count: null, ...extra });
const product = (id: number, name: string, variants: ShopPublicProduct["variants"], extra: Partial<ShopPublicProduct> = {}): ShopPublicProduct => ({
  id, slug: name.toLowerCase(), name, kind: "merch", category: "Stationery", unit: "", image_url: "", price_from: 10, price_to: 10,
  members_only: false, max_per_order: null, sold_out: false, variants, ...extra });
const products = [
  product(1, "Pen", [variant(11, { stock_count: 5 })]),
  product(2, "Tape", [variant(21, { stock_label: "low" })], { category: "Tools" }),
  product(3, "Mug", [variant(31, { sold_out: true, stock_label: "sold_out" })], { sold_out: true }),
];
const quote = { currency: "inr", lines: [{ variant_id: 11, label: "Pen", quantity: "1", unit_amount: "10.00", discount: "0", net: "10.00",
  tax_rate_bps: null, tax: null }], subtotal: "10.00", discount_total: "0", total: "10.00", tax_total: "0", amount_due: "10.00",
  tax_inclusive: true, discount_name: "", digest: "d1" };

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter><PublicShopPage /></MemoryRouter></QueryClientProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.selling = undefined;
  window.localStorage.clear();
  mocks.tenant.mockImplementation((_slug: string, path: string) => Promise.resolve(path.endsWith("/shop/") ? shop
    : path.includes("/products/") ? { count: 3, next: null, previous: null, results: products } : quote));
});

describe("public shop page", () => {
  it("keeps the visible basket action in its accessible name and names the product", async () => {
    show();
    const title = await screen.findByRole("link", { name: "Pen" });
    const row = title.closest("li")!;
    const add = within(row).getByText("Add to basket", { selector: "button", exact: true });
    expect(add).toHaveAccessibleName(/^Add to basket Pen$/);
  });

  it("keeps browsing and hides the basket when charge tracking is known to be off", async () => {
    mocks.selling = false;
    show();
    expect(await screen.findByRole("link", { name: "Pen" })).toBeVisible();
    expect(screen.getByText("In stock · 5 left")).toBeVisible();
    expect(screen.queryByRole("button", { name: /basket/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/₹10/)).not.toBeInTheDocument();
  });

  it("does not offer to add a variant whose public price has been removed", async () => {
    const redacted = product(1, "Pen", [variant(11, { price: null })], { price_from: null, price_to: null });
    mocks.tenant.mockImplementation((_slug: string, path: string) => Promise.resolve(path.endsWith("/shop/") ? shop
      : { count: 1, next: null, previous: null, results: [redacted] }));
    show();
    expect(await screen.findByRole("link", { name: "Pen" })).toBeVisible();
    expect(screen.queryByRole("button", { name: "Add to basket Pen" })).not.toBeInTheDocument();
    expect(screen.queryByText(/₹0/)).not.toBeInTheDocument();
  });

  it("labels stock and blocks sold-out items", async () => {
    show();
    expect(await screen.findByRole("link", { name: "Pen" })).toBeVisible();
    expect(screen.getByText("In stock · 5 left")).toBeVisible();
    expect(screen.getByText("Low")).toBeVisible();
    expect(screen.getByText("Sold out")).toBeVisible();
    expect(screen.getByRole("button", { name: "Add to basket Pen" })).toBeEnabled();
    expect(screen.queryByRole("button", { name: "Add to basket Mug" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Tools" })).toHaveAttribute("aria-pressed", "false");
  });

  it("adds to the basket, changes the quantity and removes the line, keeping it per space", async () => {
    show();
    fireEvent.click(await screen.findByRole("button", { name: "Add to basket Pen" }));
    const basket = await screen.findByRole("list", { name: "Basket" });
    expect(within(basket).getByText("Pen")).toBeVisible();
    expect(JSON.parse(window.localStorage.getItem("spaceworks.shop.cart:lab") ?? "[]")).toEqual([
      expect.objectContaining({ variantId: 11, quantity: 1, price: "10" })]);
    // The policy is on screen before any payment step.
    expect(screen.getByText("No refunds on cut material.")).toBeVisible();
    expect(screen.getByText("Collect at the front desk.")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "One more Pen" }));
    await waitFor(() => expect(screen.getByLabelText("2 of Pen")).toBeVisible());
    fireEvent.click(screen.getByRole("button", { name: "Remove Pen" }));
    expect(await screen.findByText("Your basket is empty.")).toBeVisible();
    expect(window.localStorage.getItem("spaceworks.shop.cart:lab")).toBeNull();
  });
});
