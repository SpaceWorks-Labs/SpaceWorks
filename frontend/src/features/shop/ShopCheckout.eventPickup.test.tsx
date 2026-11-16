import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ShopCheckout } from "./ShopCheckout";
import { rememberedPickupEvent, rememberPickupEvent } from "./pickupPreference";
import type { ShopSummary } from "./shopApi";

const mocks = vi.hoisted(() => ({ tenant: vi.fn(), member: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"),
  tenantPublicRequest: mocks.tenant, tenantMemberRequest: mocks.member }));

const fair = { id: 41, title: "Maker Fair", starts_at: "2026-12-01T10:00:00Z" };
const hidden = { id: 42, title: "Members night", starts_at: "2026-12-02T18:00:00Z" };
const shopWith = (pickup_events: ShopSummary["pickup_events"]): ShopSummary => ({ name: "Lab", currency: "inr", pay_online: false,
  guest_checkout: false, member_prices: false, policy_text: "", pickup_note: "", returns_days: 0, hold_minutes: null, pickup_events });
const quote = { currency: "inr", lines: [{ variant_id: 11, label: "Tee", quantity: "1", unit_amount: "20.00", discount: "0", net: "20.00",
  tax_rate_bps: null, tax: null }], subtotal: "20.00", discount_total: "0", total: "20.00", tax_total: "0", amount_due: "20.00",
  tax_inclusive: true, discount_name: "", digest: "d1" };
const placed = { order: { id: 9, status: "awaiting_payment", channel: "online", pickup_code: "K7Q2", pickup_at: "event",
  pickup_event_title: "Maker Fair", currency: "inr", subtotal: "20.00", discount_total: "0", total: "20.00", tax_total: "0",
  amount_due: "20.00", created_at: "2026-11-01T10:00:00Z", expires_at: null, paid_at: null, ready_at: null, collected_at: null,
  lines: [], space_name: "Lab" }, checkout_url: "", status_token: "" };
const lines = [{ variantId: 11, quantity: 1, label: "Tee", price: "20.00", productSlug: "tee" }];
const orderBodies = () => mocks.member.mock.calls.filter(([, path]) => path.endsWith("/orders/")).map(([, , init]) => JSON.parse(init.body));

function show(shop: ShopSummary) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter><ShopCheckout slug="lab" shop={shop} lines={lines} session="authenticated"
    onSession={vi.fn()} onPlaced={vi.fn()} path={(part = "") => `/m/lab/${part}`} /></MemoryRouter></QueryClientProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
  window.history.replaceState(null, "", "/m/lab/shop");
  mocks.member.mockImplementation((_slug: string, path: string) => Promise.resolve(path.endsWith("/quote/") ? quote : placed));
});

describe("shop checkout with event merch (#135 Q-S18)", () => {
  it("starts at the space when no event was chosen", async () => {
    show(shopWith([fair]));
    expect(await screen.findByLabelText("Where will you collect it?")).toHaveValue("space");
  });

  it("preselects the event an event page linked from, then forgets it once the order is placed", async () => {
    rememberPickupEvent("lab", fair);
    show(shopWith([fair]));
    expect(await screen.findByLabelText("Where will you collect it?")).toHaveValue("41");
    const place = await screen.findByRole("button", { name: "Place order, pay at the desk" });
    await waitFor(() => expect(place).toBeEnabled());
    fireEvent.click(place);
    await waitFor(() => expect(orderBodies()).toHaveLength(1));
    expect(orderBodies()[0]).toMatchObject({ pickup_at: "event", pickup_event_id: 41, lines: [{ variant_id: 11, quantity: 1 }] });
    await waitFor(() => expect(rememberedPickupEvent("lab")).toBeNull());
  });

  it("offers an unlisted event the buyer came from as its own pickup choice", async () => {
    rememberPickupEvent("lab", hidden);
    show(shopWith([fair]));
    const select = await screen.findByLabelText("Where will you collect it?");
    expect(select).toHaveValue("42");
    expect(screen.getByRole("option", { name: /Members night/ })).toBeInTheDocument();
  });

  it("follows a pasted ?pickup_event= link only to an event the shop lists", async () => {
    window.history.replaceState(null, "", "/m/lab/shop?pickup_event=41");
    show(shopWith([fair]));
    expect(await screen.findByLabelText("Where will you collect it?")).toHaveValue("41");
  });
});
