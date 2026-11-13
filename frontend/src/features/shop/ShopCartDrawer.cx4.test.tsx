import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../lib/api";
import { ShopCartDrawer } from "./ShopCartDrawer";
import type { ShopQuote, ShopSummary } from "./shopApi";
import type { CartLine } from "./useShopCart";

const h = vi.hoisted(() => ({ quote: vi.fn(), place: vi.fn(), session: "authenticated" as "authenticated" | "restoring" }));
vi.mock("./shopApi", async () => ({ ...await vi.importActual<typeof import("./shopApi")>("./shopApi"),
  quoteCart: h.quote, placeShopOrder: h.place }));
vi.mock("./useShopSpace", () => ({ useMemberSession: () => [h.session, vi.fn()] }));

const shop: ShopSummary = { name: "Lab", currency: "inr", pay_online: false, guest_checkout: false, member_prices: false,
  policy_text: "Collect at the desk.", pickup_note: "", returns_days: 0, hold_minutes: null, pickup_events: [] };
const pen: CartLine = { variantId: 11, quantity: 2, label: "Pen", price: "50.00", productSlug: "pen" };
const quote: ShopQuote = { currency: "inr", lines: [], subtotal: "100", discount_total: "0", total: "100", tax_total: "0",
  amount_due: "100", tax_inclusive: true, discount_name: "", digest: "cx4-quote" };

function show(lines: CartLine[] = [pen]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const cart = { lines, count: lines.length, add: vi.fn(), setQuantity: vi.fn(), remove: vi.fn(), clear: vi.fn() };
  const close = vi.fn();
  const view = render(<QueryClientProvider client={client}><MemoryRouter><ShopCartDrawer open onClose={close} slug="lab"
    shop={shop} cart={cart} path={(part = "") => `/m/lab/${part}`} /></MemoryRouter></QueryClientProvider>);
  return { ...view, client, cart, close };
}

beforeEach(() => { h.quote.mockReset(); h.place.mockReset(); h.session = "authenticated"; sessionStorage.clear(); });

describe("basket with real checkout state", () => {
  it("restoring sign-in neither quotes nor permits an order", () => {
    h.session = "restoring";
    show();
    expect(screen.getByText("Checking your sign-in…")).toBeVisible();
    expect(h.quote).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: "Place order, pay at the desk" })).not.toBeInTheDocument();
  });

  it("empty cart does not request a quote or offer a checkout action", () => {
    show([]);
    expect(screen.getByText("Your basket is empty.")).toBeVisible();
    expect(h.quote).not.toHaveBeenCalled();
    expect(h.place).not.toHaveBeenCalled();
  });

  it("pricing blocks checkout until the quote arrives", () => {
    h.quote.mockReturnValue(new Promise(() => {}));
    show();
    expect(screen.getByText("Pricing your basket…")).toBeVisible();
    expect(screen.getByRole("button", { name: "Place order" })).toBeDisabled();
  });

  it.each([[403, "permission_denied", "This item is private."], [404, "module_disabled", "The shop is turned off."]])(
    "a %s quote refusal preserves the basket without permitting an order", async (status, code, detail) => {
      h.quote.mockRejectedValue(new StructuredApiError(status, { code, detail }));
      show();
      expect(await screen.findByRole("alert")).toHaveTextContent(detail);
      expect(screen.getByText("Pen")).toBeVisible();
      expect(screen.getByRole("button", { name: "Place order" })).toBeDisabled();
      expect(h.place).not.toHaveBeenCalled();
    });

  it("a failed placement can be retried without clearing the cart", async () => {
    h.quote.mockResolvedValue(quote);
    h.place.mockRejectedValueOnce(new Error("Connection lost"));
    const { cart } = show();
    fireEvent.click(await screen.findByRole("button", { name: "Place order, pay at the desk" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong. Try again.");
    expect(screen.getByRole("button", { name: "Place order, pay at the desk" })).toBeEnabled();
    expect(cart.clear).not.toHaveBeenCalled();
    expect(h.place).toHaveBeenCalledTimes(1);
  });

  it("keyboard focus wraps at the sheet boundary and Escape closes it", async () => {
    h.quote.mockResolvedValue(quote);
    const { close } = show();
    await screen.findByRole("button", { name: "Place order, pay at the desk" });
    const first = screen.getByRole("button", { name: "One fewer Pen" });
    const last = screen.getByRole("button", { name: "Close dialog" });
    last.focus();
    fireEvent.keyDown(document, { key: "Tab" });
    await waitFor(() => expect(first).toHaveFocus());
    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(last).toHaveFocus();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(close).toHaveBeenCalledTimes(1);
  });
});
