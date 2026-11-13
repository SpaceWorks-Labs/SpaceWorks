import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { EventTicketShop } from "./EventTicketShop";
import { OrderSummary } from "./OrderSummary";
import type { OrderQuote, TicketShop } from "./ticketingApi";

const mocks = vi.hoisted(() => ({ member: vi.fn(), tenant: vi.fn() }));
vi.mock("../../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api"),
  memberRequest: mocks.member, tenantPublicRequest: mocks.tenant }));

const shop: TicketShop = {
  event_id: 5, orders_enabled: true, currency: "inr", booking_fee_fixed: "0", booking_fee_bps: 0, max_tickets_per_order: 4,
  promo_codes_enabled: true, policy: { text: "Ask us.", overridden: true, terms: null },
  ticket_types: [{ id: 1, name: "Early bird", amount: "10.00", audience: "public", pricing_mode: "pwyw", min_amount: "5.00",
    seats_per_ticket: 1, min_quantity: 1, per_order_limit: 0, spots_left: null, sold_out: false, next_tier: { name: "Regular", amount: "15.00" } }],
  addons: [{ id: 9, name: "T-shirt", description: "", kind: "merch", amount: "8.00", per_order_limit: 0, sold_out: false, variants: [] }],
} as unknown as TicketShop;

beforeEach(() => { vi.clearAllMocks(); mocks.tenant.mockResolvedValue(shop); });

describe("ticket orders in a free events domain (#184)", () => {
  it("runs the shop with no price, tier, pay-what-you-want amount or promo field", async () => {
    render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <EventTicketShop makerspaceSlug="lab" makerspaceId={7} publicToken="tok" ordersHref={id => `/o/${id}`} free /></QueryClientProvider>);
    expect(await screen.findByText("Early bird")).toBeVisible();
    expect(screen.getAllByText("Free").length).toBe(2);
    expect(screen.queryByText(/Next: Regular/)).toBeNull();
    expect(screen.queryByText(/10\.00|8\.00|5\.00/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "More Early bird" }));
    expect(screen.queryByText(/Amount per ticket/)).toBeNull();
    fireEvent.click(screen.getByText("Have a code?"));
    expect(screen.queryByLabelText("Promo code")).toBeNull();
  });

  it("summarises a free quote without money", () => {
    const quote = { quote: { currency: "inr", subtotal: "0", discount_total: "0", total: "0", digest: "d", mode: "free",
      lines: [{ component: "per_registration", label: "Ticket", quantity: "2", unit_amount: "0", gross: "0", discount: "0", net: "0", detail: { label: "Early bird" } }] },
      promo_saving: null, seats: 2, policy: shop.policy } as unknown as OrderQuote;
    render(<OrderSummary quote={quote} />);
    expect(screen.getByText("Early bird × 2")).toBeVisible();
    expect(screen.getByText("Free")).toBeVisible();
    expect(screen.queryByText(/0\.00|₹/)).toBeNull();
  });
});
