import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { MemberPaymentRows, type MemberPayment } from "./MemberPayments";

const base: MemberPayment = {
  id: 5,
  subject_type: "loan_deposit",
  subject_label: "Loan deposit - request #12",
  status: "paid_online",
  amount: "10.00",
  currency: "usd",
  due_date: null,
  due_state: "none",
  checkout_url: "",
  online_payment_available: true,
  settlement: null,
  refunded_amount: 4,
  refunds: [],
  created_at: "2026-10-01T10:00:00Z",
  offline_collection: { upi: null, instructions: "", claim: null, claimable: false },
};

describe("MemberPaymentRows", () => {
  it("shows the payer the refunds recorded on their charge, never a failed attempt", () => {
    render(
      <MemberPaymentRows
        onCheckout={vi.fn()}
        payments={[{
          ...base,
          refunds: [
            { amount: "4.00", currency: "usd", status: "succeeded", reason: "returned early", settled_at: "2026-10-02T10:00:00Z", method: "", reference: "", refunded_at: null },
            { amount: "1.00", currency: "usd", status: "pending", reason: "", settled_at: null, method: "", reference: "", refunded_at: null },
            { amount: "2.00", currency: "usd", status: "failed", reason: "", settled_at: "2026-10-02T11:00:00Z", method: "", reference: "", refunded_at: null },
          ],
        }]}
      />,
    );

    expect(screen.getByText(/Refunded/)).toHaveTextContent("Refunded $4.00 (returned early)");
    expect(screen.getByText(/Refund pending/)).toHaveTextContent("Refund pending $1.00");
    expect(screen.queryByText(/2\.00 USD/)).toBeNull();
  });

  it("offers a live link from either rail and nothing for a settled charge", () => {
    render(
      <MemberPaymentRows
        onCheckout={vi.fn()}
        payments={[
          { ...base, id: 6, status: "pending", checkout_url: "https://rzp.io/i/live" },
          { ...base, id: 7, status: "paid_offline" },
        ]}
      />,
    );

    const pay = screen.getByRole("link", { name: "Pay now" });
    expect(pay).toHaveAttribute("href", "https://rzp.io/i/live");
    expect(screen.queryAllByRole("link", { name: "Pay now" })).toHaveLength(1);
  });

  it("offers no second, online payment while the payer's \"I paid\" note waits for staff", () => {
    const claim = { id: 1, reference: "UTR123456", paid_on: "2026-11-01", decision_note: "", method: "upi" as const, created_at: "2026-11-01T10:00:00Z" };
    render(
      <MemberPaymentRows
        onCheckout={vi.fn()}
        payments={[
          { ...base, id: 8, status: "pending", subject_label: "Claimed", offline_collection: { upi: null, instructions: "", claimable: false, claim: { ...claim, status: "submitted" } } },
          { ...base, id: 9, status: "pending", subject_label: "Rejected claim", offline_collection: { upi: null, instructions: "", claimable: true, claim: { ...claim, status: "rejected" } } },
        ]}
      />,
    );
    expect(screen.getAllByRole("button", { name: "Generate payment link" })).toHaveLength(1);
  });

  it("shows a pending donation as an unfinished gift, not a debt", () => {
    render(<MemberPaymentRows onCheckout={vi.fn()} payments={[{ ...base, subject_type: "donation", status: "pending" }]} />);
    expect(screen.getByText("Gift not completed")).toBeVisible();
    expect(screen.queryByText("Pending")).toBeNull();
  });

  it.each([
    ["jpy", "1200.00", /1,200(?!\.)/],
    ["kwd", "1.25", /1\.250/],
  ])("shows a %s charge with that currency's minor-unit digits", (currency, amount, shown) => {
    render(<MemberPaymentRows onCheckout={vi.fn()} payments={[{ ...base, currency, amount }]} />);
    expect(screen.getByText(shown)).toBeVisible();
  });
});
