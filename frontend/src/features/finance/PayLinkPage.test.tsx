import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../lib/api";
import { PayLinkPage } from "./PayLinkPage";

const finance = vi.hoisted(() => ({ payLinkRequest: vi.fn() }));
vi.mock("./financeApi", () => finance);

const link = {
  makerspace: "Lab", label: "Shop order", amount: "1200.00", currency: "jpy", status: "pending",
  expires_at: "2026-12-01T00:00:00Z", online_available: true,
  upi: null, instructions: "", claim: null, claimable: false,
};

function mount(path: string) {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>
    <MemoryRouter initialEntries={[path]}><Routes><Route path="/pay/:token" element={<PayLinkPage />} /></Routes></MemoryRouter>
  </QueryClientProvider>);
}

beforeEach(() => { vi.resetAllMocks(); });

describe("PayLinkPage", () => {
  it("does not thank a payer whose checkout was cancelled", () => {
    mount("/pay/complete?checkout=cancelled");
    expect(screen.getByText("Payment cancelled")).toBeVisible();
    expect(screen.queryByText("Thank you")).toBeNull();
    expect(finance.payLinkRequest).not.toHaveBeenCalled();
  });

  it("thanks a payer whose checkout succeeded", () => {
    mount("/pay/complete?checkout=success");
    expect(screen.getByText("Thank you")).toBeVisible();
  });

  it("shows the amount in the currency's own digits (JPY has none)", async () => {
    finance.payLinkRequest.mockResolvedValue(link);
    mount("/pay/tok123");
    expect(await screen.findByText(/Pay .*1,200(?!\.)/)).toBeVisible();
  });

  it("explains why online payment was refused while an offline payment awaits staff", async () => {
    finance.payLinkRequest.mockImplementation(async (path: string) => {
      if (path.endsWith("/checkout")) throw new StructuredApiError(409, { detail: "x", code: "payment_settlement_pending" });
      return link;
    });
    mount("/pay/tok123");
    fireEvent.click(await screen.findByRole("button", { name: "Pay online" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Wait for them to confirm it before paying again");
  });

  it("says a cancelled or waived charge no longer needs paying rather than calling it settled", async () => {
    finance.payLinkRequest.mockResolvedValue({ ...link, status: "canceled" });
    mount("/pay/tok123");
    expect(await screen.findByText("This charge no longer needs paying.")).toBeVisible();
  });
});
