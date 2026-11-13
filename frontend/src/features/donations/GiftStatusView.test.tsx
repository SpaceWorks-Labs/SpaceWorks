import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { GiftStatusView } from "./GiftStatusView";
import type { GiftStatus } from "./donationsApi";

// MOD-3 flow audit (donations: a giver's own gift screen): each status shows only the actions it may take.
vi.mock("../members/MemberPaymentOffline", () => ({ useUpiQr: (uri: string | null) => (uri ? "data:image/png;base64,AAAA" : null) }));

const gift = (over: Partial<GiftStatus> = {}): GiftStatus => ({
  amount: "750.00", currency: "inr", makerspace: "The Lab", campaign: "New laser", status: "pending", payment_status: "pending",
  created_at: "2026-11-01T10:00:00Z", paid_at: null, receipt_number: "", receipt_note: "", donor_pan_masked: "", tax_receipt_number: "",
  checkout_url: "", status_token: "", online_available: true, offline: null, ...over,
} as unknown as GiftStatus);

describe("GiftStatusView", () => {
  it("pending: shows waiting, offers Pay online once, and the fallback offline note when no instructions exist", () => {
    const onPay = vi.fn();
    render(<GiftStatusView gift={gift()} onPayOnline={onPay} />);
    expect(screen.getByText("Waiting for payment")).toBeInTheDocument();
    expect(screen.getByText("₹750.00")).toBeInTheDocument();
    expect(screen.getByText("The Lab · New laser")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Pay online" }));
    expect(onPay).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/The space will tell you how to pay/)).toBeInTheDocument();
    expect(screen.queryByText("Thank you. Your gift has been received.")).not.toBeInTheDocument();
  });

  it("pending while the checkout opens: the pay button is disabled so a double click cannot start two checkouts", () => {
    render(<GiftStatusView gift={gift()} onPayOnline={() => {}} paying />);
    expect(screen.getByRole("button", { name: /Opening checkout/ })).toBeDisabled();
  });

  it("pending with the online rail unavailable: no Pay online button, offline instructions and UPI QR shown", () => {
    render(<GiftStatusView gift={gift({ online_available: false, offline: { instructions: "Pay at the desk", upi: { uri: "upi://pay?pa=lab@bank", vpa: "lab@bank" } } as GiftStatus["offline"] })}
      onPayOnline={() => {}} />);
    expect(screen.queryByRole("button", { name: "Pay online" })).not.toBeInTheDocument();
    expect(screen.getByText("Pay at the desk")).toBeInTheDocument();
    expect(screen.getByText("lab@bank")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /UPI QR code to pay/ })).toBeInTheDocument();
  });

  it("paid: thanks, receipt numbers, a tax receipt download only with its link, and no payment actions", () => {
    const { rerender } = render(<GiftStatusView gift={gift({ status: "paid", receipt_number: "R-9", tax_receipt_number: "T-4", donor_pan_masked: "XXXXX1234X" })} onPayOnline={() => {}} />);
    expect(screen.getByText("Received")).toBeInTheDocument();
    expect(screen.getByText("Thank you. Your gift has been received.")).toBeInTheDocument();
    expect(screen.getByText("R-9")).toBeInTheDocument();
    expect(screen.getByText("XXXXX1234X")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Download tax receipt/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Pay online" })).not.toBeInTheDocument();
    rerender(<GiftStatusView gift={gift({ status: "paid", tax_receipt_number: "T-4" })} taxReceiptHref="/receipts/T-4.pdf" />);
    expect(screen.getByRole("link", { name: /Download tax receipt/ })).toHaveAttribute("href", "/receipts/T-4.pdf");
  });

  it("cancelled: neutral status and no way to pay", () => {
    render(<GiftStatusView gift={gift({ status: "cancelled" })} onPayOnline={() => {}} />);
    expect(screen.getByText("Cancelled")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Pay online" })).not.toBeInTheDocument();
    expect(screen.queryByText(/Pay offline|The space will tell you/)).not.toBeInTheDocument();
  });
});
