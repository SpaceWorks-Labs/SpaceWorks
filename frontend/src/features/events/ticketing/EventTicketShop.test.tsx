import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../../lib/api";
import { EventTicketShop } from "./EventTicketShop";
import type { TicketShop } from "./ticketingApi";

const mocks = vi.hoisted(() => ({ member: vi.fn(), tenant: vi.fn() }));
vi.mock("../../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api"),
  memberRequest: mocks.member, tenantPublicRequest: mocks.tenant }));

const shop: TicketShop = {
  event_id: 5, orders_enabled: true, currency: "inr", booking_fee_fixed: "1.00", booking_fee_bps: 0, max_tickets_per_order: 4,
  promo_codes_enabled: true, policy: { text: "Ask us.", overridden: true, terms: { full_before_minutes: "1440", partial_before_minutes: "60", partial_percent: "50", cancellation_fee: "0" } },
  ticket_types: [
    { id: 1, name: "Early bird", amount: "10.00", audience: "public", pricing_mode: "fixed", min_amount: "0", seats_per_ticket: 1,
      min_quantity: 1, per_order_limit: 0, spots_left: 3, sold_out: false, next_tier: { name: "Regular", amount: "15.00" } },
    { id: 2, name: "Supporter", amount: "20.00", audience: "public", pricing_mode: "pwyw", min_amount: "5.00", seats_per_ticket: 1,
      min_quantity: 1, per_order_limit: 0, spots_left: null, sold_out: false, next_tier: null },
  ],
  addons: [{ id: 9, name: "T-shirt", description: "", kind: "merch", amount: "8.00", per_order_limit: 0, sold_out: false,
    variants: [{ id: 3, label: "M", sold_out: false }, { id: 4, label: "L", sold_out: true }] }],
};
const quote = { quote: { currency: "inr", subtotal: "20.00", discount_total: "0", total: "21.00", digest: "abc",
  lines: [{ component: "per_registration", label: "Per registration", quantity: "2", unit_amount: "10.00", gross: "20.00", discount: "0", net: "20.00", detail: { label: "Early bird" } },
    { component: "booking_fee", label: "Booking fee", quantity: "1", unit_amount: "1.00", gross: "1.00", discount: "0", net: "1.00", detail: {} }] },
  promo_saving: null, seats: 2, policy: shop.policy };

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><EventTicketShop makerspaceSlug="lab" makerspaceId={7} publicToken="tok"
    ordersHref={id => `/member/orders/${id}`} /></QueryClientProvider>);
}

beforeEach(() => { vi.clearAllMocks(); mocks.tenant.mockResolvedValue(shop); });

describe("event ticket shop", () => {
  it("shows tiers, the next-tier hint, the policy and sold-out variants", async () => {
    show();
    expect(await screen.findByText("Early bird")).toBeVisible();
    expect(screen.getByText(/Next: Regular/)).toBeVisible();
    expect(screen.getByText(/Full refund until 24 h before the start/)).toBeVisible();
    expect(screen.getByRole("option", { name: "L (sold out)" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Review order" })).toBeDisabled();
  });

  it("prices the basket on the server, then places the order with the shown digest", async () => {
    mocks.member.mockImplementation((path: string) => Promise.resolve(path.endsWith("/quote/") ? quote
      : { order: { id: 44 }, checkout_url: "" }));
    const assign = vi.fn();
    Object.defineProperty(window, "location", { value: { ...window.location, assign }, writable: true });
    show();
    fireEvent.click(await screen.findByRole("button", { name: "More Early bird" }));
    fireEvent.click(screen.getByRole("button", { name: "More Early bird" }));
    fireEvent.click(screen.getByRole("button", { name: "Review order" }));
    expect(await screen.findByText("Your order")).toBeVisible();
    const [path, init] = mocks.member.mock.calls[0];
    expect(path).toBe("/member/makerspaces/7/events/5/orders/quote/");
    expect(JSON.parse(init.body).tickets).toEqual([{ ticket_type_id: 1, quantity: 2 }]);
    fireEvent.click(screen.getByRole("button", { name: "Continue to payment" }));
    await waitFor(() => expect(assign).toHaveBeenCalledWith("/member/orders/44"));
    expect(JSON.parse(mocks.member.mock.calls[1][1].body).digest).toBe("abc");
  });

  it("explains a sold-out refusal", async () => {
    mocks.member.mockRejectedValue(new StructuredApiError(409, { detail: "x", code: "sold_out" }));
    show();
    fireEvent.click(await screen.findByRole("button", { name: "More Supporter" }));
    expect(screen.getByLabelText(/Amount per ticket/)).toHaveValue("20.00");
    fireEvent.click(screen.getByRole("button", { name: "Review order" }));
    expect(await screen.findByText("Not enough places are left for that choice.")).toBeVisible();
  });
});
