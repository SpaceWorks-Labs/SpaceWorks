import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { tenantPublicRequest } from "../../lib/api";
import { PricePreview } from "./PricePreview";
import { quoteReady, type PricingPublicQuote } from "./usePriceQuote";

vi.mock("../../lib/api", () => ({ tenantPublicRequest: vi.fn() }));
// useChargesOn (#184 G5, 14992cc1) reads the tenant: a single space whose events/bookings/loans charge.
vi.mock("../../lib/tenant", async (importOriginal) => ({ ...await importOriginal<typeof import("../../lib/tenant")>(),
  useTenant: () => ({ mode: "single", bootstrap: { charges_tracked: { events: true, bookings: true, loans: true } } }) }));

const line = { component: "rental_per_day", label: "Rental per day", subject_type: "loan", quantity: "3.0000", unit_amount: "50.00",
  gross: "150.00", discount: "15.00", net: "135.00", source: "default", cap_applied: false, target: null, detail: {} };

const quote = (overrides: Partial<PricingPublicQuote> = {}): PricingPublicQuote => ({
  quote: { domain: "loans", currency: "usd", mode: "paid", lines: [line], subtotal: "150.00", discount_total: "15.00", total: "135.00",
    discount: { id: 1, name: "Members", audience: "all_members", saving: "15.00" }, waiver: null, notes: [], digest: "abc" },
  digest: "abc",
  tax: { net: "135.00", tax: "0.00", gross: "135.00", inclusive: false, mode: "none" },
  members_total: null, member_price_applied: true,
  deposit: { amount: "500.00", refundable: true },
  policy: { late_per_day: "20.00", late_cap: "100.00", grace_days: 1, damage_default: "0.00", lost_default: "0.00",
    damage_lost_text: "Staff set damage and lost charges at return, only with a return photo." },
  refund_summary: null,
  ...overrides,
});

const loans = { domain: "loans" as const, items: [{ product_id: 4, quantity: 1 }] };

function show(node: ReactNode) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{node}</QueryClientProvider>);
}

describe("PricePreview", () => {
  beforeEach(() => { vi.mocked(tenantPublicRequest).mockReset(); });

  it("posts the request and shows lines, discount, total, deposit and policy", async () => {
    vi.mocked(tenantPublicRequest).mockResolvedValue(quote());
    const onDigest = vi.fn();
    show(<PricePreview makerspaceSlug="lab" request={loans} onDigest={onDigest} />);
    expect(await screen.findByText("Rental per day")).toBeVisible();
    expect(tenantPublicRequest).toHaveBeenCalledWith("lab", "/public/lab/pricing/quote", { method: "POST", body: JSON.stringify(loans) });
    expect(screen.getByText(/Member discount \(Members\)/)).toBeVisible();
    expect(screen.getByText("Total").parentElement).toHaveTextContent("$135.00");
    expect(screen.getByText(/Refundable deposit:/)).toHaveTextContent("$500.00");
    expect(screen.getByText(/Late returns: \$20.00 per day after 1 grace day, up to \$100.00/)).toBeVisible();
    expect(screen.getByText(/only with a return photo/)).toBeVisible();
    expect(onDigest).toHaveBeenCalledWith("abc");
  });

  it("splits tax and shows the members' price and waiver", async () => {
    vi.mocked(tenantPublicRequest).mockResolvedValue(quote({
      tax: { net: "135.00", tax: "13.50", gross: "148.50", inclusive: false, mode: "exclusive" },
      members_total: "120.00", deposit: null, policy: null,
      quote: { ...quote().quote, discount_total: "0.00", discount: null, waiver: { reason: "Staff" } },
    }));
    show(<PricePreview makerspaceSlug="lab" request={loans} />);
    expect(await screen.findByText("Tax")).toBeVisible();
    expect(screen.getByText("Total").parentElement).toHaveTextContent("$148.50");
    expect(screen.getByText(/Members pay/)).toHaveTextContent("$120.00");
    expect(screen.getByText("Fees waived")).toBeVisible();
  });

  it("says Free when nothing is owed", async () => {
    vi.mocked(tenantPublicRequest).mockResolvedValue(quote({
      quote: { ...quote().quote, lines: [], total: "0.00", discount_total: "0.00", discount: null }, deposit: null, policy: null,
    }));
    show(<PricePreview makerspaceSlug="lab" request={{ domain: "membership", joining: true }} />);
    expect(await screen.findByText("Free")).toBeVisible();
    expect(screen.queryByText("Total")).toBeNull();
  });

  it("renders nothing on 404 and a quiet notice on 429", async () => {
    vi.mocked(tenantPublicRequest).mockImplementationOnce(async () => { throw Object.assign(new Error("off"), { status: 404 }); });
    const { container } = show(<PricePreview makerspaceSlug="lab" request={loans} />);
    await waitFor(() => expect(tenantPublicRequest).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
    vi.mocked(tenantPublicRequest).mockImplementationOnce(async () => { throw Object.assign(new Error("slow"), { status: 429 }); });
    show(<PricePreview makerspaceSlug="lab" request={{ domain: "machines", machine_id: 2 }} />);
    expect(await screen.findByText("Price preview unavailable right now")).toBeVisible();
  });

  it("does not ask until there is something to price", () => {
    const { container } = show(<PricePreview makerspaceSlug="lab" request={{ domain: "loans", items: [] }} />);
    expect(container).toBeEmptyDOMElement();
    expect(tenantPublicRequest).not.toHaveBeenCalled();
    expect(quoteReady({ domain: "bookings", space_id: 1 })).toBe(false);
    expect(quoteReady({ domain: "events", event_id: 3 })).toBe(true);
  });

  it("marks the price region live for screen readers", async () => {
    vi.mocked(tenantPublicRequest).mockResolvedValue(quote());
    show(<PricePreview makerspaceSlug="lab" request={loans} />);
    await screen.findByText("Rental per day");
    expect(document.querySelector('[aria-live="polite"]')).not.toBeNull();
  });
});
