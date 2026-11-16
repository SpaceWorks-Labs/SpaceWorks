import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../lib/api";
import type { GiftStatus } from "./donationsApi";
import { GuestGiftPage } from "./GuestGiftPage";

// MOD-3B frontend states: loading, error + retry, expired link (permission denied), pending/paid, checkout failure.
const { gift, checkout } = vi.hoisted(() => ({ gift: vi.fn(), checkout: vi.fn() }));
vi.mock("./donationsApi", async () => ({
  ...await vi.importActual<typeof import("./donationsApi")>("./donationsApi"),
  donationsApi: { gift, checkout, taxReceiptUrl: (token: string) => `/tax/${token}.pdf` },
}));
vi.mock("./GuestPaidClaim", () => ({ GuestPaidClaim: () => <p>claim-form</p> }));
vi.mock("../members/MemberPaymentOffline", () => ({ useUpiQr: () => null }));
vi.mock("./DonationShell", () => ({
  DonationShell: ({ title, state, children }: { title: string; state: { status: string; error?: string; onRetry?: () => void };
    children: ReactNode }) => <main><h1>{title}</h1>
    {state.status === "loading" ? <p role="status">loading</p> : null}
    {state.status === "error" ? <div role="alert">{state.error}<button type="button" onClick={state.onRetry}>Retry</button></div> : null}
    {state.status === "ready" ? children : null}</main>,
}));

const row = (over: Partial<GiftStatus> = {}): GiftStatus => ({
  id: 7, amount: "750.00", currency: "inr", makerspace: "The Lab", campaign: "", status: "pending", payment_status: "pending",
  created_at: "2026-11-01T10:00:00Z", paid_at: null, receipt_number: "", receipt_note: "", donor_pan_masked: "",
  tax_receipt_number: "", checkout_url: "", status_token: "", online_available: true, offline: null, ...over,
} as unknown as GiftStatus);
const assign = vi.fn();

function show(token = "signed-token") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<MemoryRouter initialEntries={[`/gift/${token}`]}><QueryClientProvider client={client}>
    <Routes><Route path="/gift/:token" element={<GuestGiftPage />} /></Routes></QueryClientProvider></MemoryRouter>);
}
const notFound = () => new StructuredApiError(404, { detail: "nope", code: "not_found" });

beforeEach(() => {
  Object.defineProperty(window, "location", { configurable: true, value: { ...window.location, assign } });
});
afterEach(() => { gift.mockReset(); checkout.mockReset(); assign.mockReset(); });

describe("GuestGiftPage states", () => {
  it("loading: shows the loading state and no gift details yet", () => {
    gift.mockReturnValue(new Promise(() => {}));
    show();
    expect(screen.getByRole("status")).toHaveTextContent("loading");
    expect(screen.queryByText("₹750.00")).not.toBeInTheDocument();
  });

  it("error: names the failure and the retry button loads the gift", async () => {
    gift.mockRejectedValueOnce(new Error("boom")).mockResolvedValueOnce(row());
    show();
    expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't load your gift.");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("₹750.00")).toBeInTheDocument();
    expect(gift).toHaveBeenCalledTimes(2);
  });

  it("an expired or foreign link (404) shows the invalid-link note and never the gift", async () => {
    gift.mockRejectedValue(notFound());
    show("forged");
    expect(await screen.findByText(/This link isn't valid any more/)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(gift).toHaveBeenCalledWith("forged");
  });

  it("pending offline gift: shows the claim form and the keep-private warning, with Pay online reachable by keyboard", async () => {
    gift.mockResolvedValue(row({ offline: { instructions: "Pay at the desk", upi: null, claimable: true } }));
    show();
    expect(await screen.findByText("Waiting for payment")).toBeInTheDocument();
    expect(screen.getByText("claim-form")).toBeInTheDocument();
    expect(screen.getByText(/Keep this link private/)).toBeInTheDocument();
    const pay = screen.getByRole("button", { name: "Pay online" });
    pay.focus();
    expect(pay).toHaveFocus();
  });

  it("paid gift: thanks the giver and offers neither Pay online nor the claim form", async () => {
    gift.mockResolvedValue(row({ status: "paid", paid_at: "2026-11-02T10:00:00Z" }));
    show();
    expect(await screen.findByText("Thank you. Your gift has been received.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Pay online" })).not.toBeInTheDocument();
    expect(screen.queryByText("claim-form")).not.toBeInTheDocument();
  });

  it("Pay online redirects to the provider checkout url", async () => {
    gift.mockResolvedValue(row());
    checkout.mockResolvedValue(row({ checkout_url: "https://pay.example/s" }));
    show();
    fireEvent.click(await screen.findByRole("button", { name: "Pay online" }));
    await waitFor(() => expect(assign).toHaveBeenCalledWith("https://pay.example/s"));
    expect(checkout).toHaveBeenCalledWith("signed-token");
  });

  it("a checkout failure (online payments off) keeps the gift and says to pay offline", async () => {
    gift.mockResolvedValue(row());
    checkout.mockRejectedValue(new StructuredApiError(409, { detail: "off", code: "payments_unavailable" }));
    show();
    fireEvent.click(await screen.findByRole("button", { name: "Pay online" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Online payment isn't available right now");
    expect(assign).not.toHaveBeenCalled();
    expect(screen.getByText("₹750.00")).toBeInTheDocument();
  });
});
