import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { OrderSummary } from "./OrderSummary";
import type { OrderQuote } from "./ticketingApi";

const quote: OrderQuote = {
  quote: { currency: "inr", subtotal: "30.00", discount_total: "5.00", total: "26.00", digest: "abc", lines: [
    { component: "per_registration", label: "Per registration", quantity: "3", unit_amount: "10.00", gross: "30.00",
      discount: "5.00", net: "25.00", detail: { label: "Early bird" } },
    { component: "booking_fee", label: "Booking fee", quantity: "1", unit_amount: "1.00", gross: "1.00", discount: "0",
      net: "1.00", detail: {} },
  ] },
  promo_saving: "5.00", seats: 3,
  policy: { text: "Ask us.", overridden: true,
    terms: { full_before_minutes: "2880", partial_before_minutes: "120", partial_percent: "50", cancellation_fee: "0" } },
};

describe("order summary", () => {
  it("shows every line, the discount, the booking fee, the total and the refund policy before payment", () => {
    render(<OrderSummary quote={quote} />);
    const summary = screen.getByRole("region", { name: "Order summary" });
    expect(summary).toHaveTextContent("Early bird × 3");
    expect(summary.querySelector("s")?.textContent).toMatch(/30/);
    expect(summary).toHaveTextContent("Booking fee");
    expect(summary).not.toHaveTextContent("Booking fee ×");
    expect(summary).toHaveTextContent(/Total.*26/);
    expect(summary).toHaveTextContent("3 places");
    expect(screen.getByText(/Full refund until 48 h before the start, 50% until 2 h before\. Ask us\./)).toBeVisible();
  });

  it("falls back to case-by-case wording without terms", () => {
    render(<OrderSummary quote={{ ...quote, seats: 1, policy: { text: "", overridden: false, terms: null } }} />);
    expect(screen.getByText("1 place", { exact: false })).toBeVisible();
    expect(screen.getByText("Refunds are decided by the organisers case by case.")).toBeVisible();
  });
});
