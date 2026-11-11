import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../lib/api";
import { ShopCheckout } from "./ShopCheckout";
import type { ShopSummary } from "./shopApi";

const mocks = vi.hoisted(() => ({ tenant: vi.fn(), member: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"),
  tenantPublicRequest: mocks.tenant, tenantMemberRequest: mocks.member }));

const shop: ShopSummary = { name: "Lab", currency: "inr", pay_online: false, guest_checkout: true, member_prices: false,
  policy_text: "Policy text.", pickup_note: "", returns_days: 0, hold_minutes: null, pickup_events: [] };
const quoteOf = (total: string, digest: string) => ({ currency: "inr", lines: [{ variant_id: 11, label: "Pen", quantity: "2", unit_amount: "50.00",
  discount: "0", net: total, tax_rate_bps: null, tax: null }], subtotal: total, discount_total: "0", total, tax_total: "0", amount_due: total,
  tax_inclusive: true, discount_name: "", digest });
const placed = { order: { id: 9, status: "held", channel: "online", pickup_code: "K7Q2", pickup_at: "space", pickup_event_title: "", currency: "inr",
  subtotal: "100.00", discount_total: "0", total: "100.00", tax_total: "0", amount_due: "100.00", created_at: "2026-11-01T10:00:00Z",
  expires_at: null, paid_at: null, ready_at: null, collected_at: null, lines: [], space_name: "Lab" }, checkout_url: "", status_token: "tok" };
const lines = [{ variantId: 11, quantity: 2, label: "Pen", price: "50.00", productSlug: "pen" }];
const bodies = () => mocks.tenant.mock.calls.filter(([, path]) => path.endsWith("/orders/")).map(([, , init]) => JSON.parse(init.body));
const keys = () => mocks.tenant.mock.calls.filter(([, path]) => path.endsWith("/orders/")).map(([, , init]) => init.headers["Idempotency-Key"]);

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const onPlaced = vi.fn();
  render(<QueryClientProvider client={client}><MemoryRouter><ShopCheckout slug="lab" shop={shop} lines={lines} session="anonymous"
    onSession={vi.fn()} onPlaced={onPlaced} path={(part = "") => `/m/lab/${part}`} /></MemoryRouter></QueryClientProvider>);
  return onPlaced;
}

async function fillGuest() {
  fireEvent.change(await screen.findByLabelText("Your name"), { target: { value: "Asha" } });
  fireEvent.change(screen.getByLabelText("Email"), { target: { value: "asha@example.com" } });
  fireEvent.click(screen.getByRole("button", { name: "Email me a code" }));
  fireEvent.change(await screen.findByLabelText("Code from the email"), { target: { value: "123456" } });
}

beforeEach(() => { vi.clearAllMocks(); });

describe("shop checkout", () => {
  it("lets a guest confirm their email with a code, then shows the pickup code for paying at the desk", async () => {
    mocks.tenant.mockImplementation((_slug: string, path: string) => Promise.resolve(path.endsWith("/quote/") ? quoteOf("100.00", "d1")
      : path.endsWith("/email-code/") ? undefined : placed));
    const onPlaced = show();
    expect(await screen.findByText("Policy text.")).toBeVisible();
    expect(await screen.findByRole("region", { name: "Your order" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Place order, pay at the desk" })).toBeDisabled();
    await fillGuest();
    expect(mocks.tenant).toHaveBeenCalledWith("lab", "/public/m/lab/shop/email-code/", expect.objectContaining({ body: JSON.stringify({ email: "asha@example.com" }) }));
    fireEvent.click(screen.getByRole("button", { name: "Place order, pay at the desk" }));
    expect(await screen.findByText("K7Q2")).toBeVisible();
    expect(bodies()[0]).toMatchObject({ quote_digest: "d1", pickup_at: "space", guest_name: "Asha", guest_email: "asha@example.com", email_code: "123456",
      lines: [{ variant_id: 11, quantity: 2 }] });
    expect(onPlaced).toHaveBeenCalled();
    expect(screen.getByRole("link", { name: "Follow this order" })).toHaveAttribute("href", "/m/lab/shop/order/tok");
  });

  it("shows the new total when prices changed and places the order on the new digest once confirmed", async () => {
    let orders = 0;
    mocks.tenant.mockImplementation((_slug: string, path: string) => {
      if (path.endsWith("/quote/")) return Promise.resolve(quoteOf("100.00", "d1"));
      if (path.endsWith("/email-code/")) return Promise.resolve(undefined);
      orders += 1;
      return orders === 1 ? Promise.reject(new StructuredApiError(409, { detail: "Prices changed.", code: "price_changed", quote: quoteOf("120.00", "d2") }))
        : Promise.resolve(placed);
    });
    show();
    await fillGuest();
    fireEvent.click(screen.getByRole("button", { name: "Place order, pay at the desk" }));
    expect(await screen.findByText(/This is the new total/)).toBeVisible();
    expect(screen.getAllByText(/120/).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "Confirm the new total" }));
    await waitFor(() => expect(bodies()).toHaveLength(2));
    expect(bodies()[1].quote_digest).toBe("d2");
    expect(await screen.findByText("K7Q2")).toBeVisible();
    // The refused first attempt placed nothing, so the confirmed one is a new attempt with its own key.
    expect(keys()[0]).not.toBe(keys()[1]);
  });

  it("sends the same Idempotency-Key when the order is submitted again after a lost response", async () => {
    let orders = 0;
    mocks.tenant.mockImplementation((_slug: string, path: string) => {
      if (path.endsWith("/quote/")) return Promise.resolve(quoteOf("100.00", "d1"));
      if (path.endsWith("/email-code/")) return Promise.resolve(undefined);
      orders += 1;
      return orders === 1 ? Promise.reject(new TypeError("Failed to fetch")) : Promise.resolve(placed);
    });
    show();
    await fillGuest();
    fireEvent.click(screen.getByRole("button", { name: "Place order, pay at the desk" }));
    expect(await screen.findByText("Something went wrong. Try again.")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Place order, pay at the desk" }));
    expect(await screen.findByText("K7Q2")).toBeVisible();
    expect(keys()).toHaveLength(2);
    expect(keys()[0]).toMatch(/^[0-9a-f-]{36}$/);
    expect(keys()[1]).toBe(keys()[0]);
  });

  it("does not place a second order while the first is still being placed", async () => {
    let finish: (value: unknown) => void = () => undefined;
    mocks.tenant.mockImplementation((_slug: string, path: string) => path.endsWith("/quote/") ? Promise.resolve(quoteOf("100.00", "d1"))
      : path.endsWith("/email-code/") ? Promise.resolve(undefined) : new Promise(resolve => { finish = resolve; }));
    show();
    await fillGuest();
    const button = screen.getByRole("button", { name: "Place order, pay at the desk" });
    fireEvent.click(button);
    fireEvent.click(button);
    expect(await screen.findByRole("button", { name: "Placing your order…" })).toBeDisabled();
    finish(placed);
    expect(await screen.findByText("K7Q2")).toBeVisible();
    expect(keys()).toHaveLength(1);
  });
});
