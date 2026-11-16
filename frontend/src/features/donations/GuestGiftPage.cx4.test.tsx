import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../lib/api";
import { GuestGiftPage } from "./GuestGiftPage";
import { donationKeys, type GiftStatus } from "./donationsApi";

const { gift, checkout } = vi.hoisted(() => ({ gift: vi.fn(), checkout: vi.fn() }));
vi.mock("./donationsApi", async () => ({ ...await vi.importActual<typeof import("./donationsApi")>("./donationsApi"),
  donationsApi: { gift, checkout, taxReceiptUrl: () => "/tax.pdf" } }));
vi.mock("./GuestPaidClaim", () => ({ GuestPaidClaim: () => <p>Claim payment</p> }));
vi.mock("../members/MemberPaymentOffline", () => ({ useUpiQr: () => null }));
vi.mock("./DonationShell", () => ({ DonationShell: ({ children, state }: { children: ReactNode;
  state: { status: string; error?: string; onRetry?: () => void } }) => <main>
  {state.status === "loading" ? <p role="status">Loading</p> : state.status === "error"
    ? <div role="alert">{state.error}{state.onRetry ? <button onClick={state.onRetry}>Retry</button> : null}</div> : children}
</main> }));

const row: GiftStatus = { id: 7, amount: "750.00", currency: "inr", makerspace: "Lab", campaign: "",
  status: "pending", payment_status: "pending", created_at: "2026-11-01T10:00:00Z", paid_at: null,
  receipt_number: "", tax_receipt_number: "", donor_pan_masked: "", checkout_url: "", status_token: "",
  online_available: true, offline: null };

function show(path = "/gift/signed") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<MemoryRouter initialEntries={[path]}><QueryClientProvider client={client}><Routes>
    <Route path="/gift/:token?" element={<GuestGiftPage />} />
  </Routes></QueryClientProvider></MemoryRouter>);
  return client;
}

beforeEach(() => { gift.mockReset(); checkout.mockReset(); });

describe("guest gift absent data, refusal and settlement refresh", () => {
  it("an absent token makes no request and reveals no gift or payment action", () => {
    show("/gift");
    expect(gift).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: "Pay online" })).not.toBeInTheDocument();
  });

  // Decision 588 (supersedes the earlier refusal retry): Retry only for 5xx, 429 or no response.
  it("an initial permission refusal shows no gift details and no Retry", async () => {
    gift.mockRejectedValueOnce(new StructuredApiError(403, { code: "permission_denied", detail: "Private" }));
    const client = show();
    expect(await screen.findByRole("alert")).toHaveTextContent("Private");
    const error = client.getQueryState(donationKeys.gift("signed"))!.error as StructuredApiError;
    expect({ status: error.status, code: error.code }).toEqual({ status: 403, code: "permission_denied" });
    expect(screen.queryByText("₹750.00")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
    expect(gift).toHaveBeenCalledTimes(1);
  });

  it("an initial outage can be retried without displaying gift details first", async () => {
    gift.mockRejectedValueOnce(new StructuredApiError(503, { code: "service_unavailable", detail: "Down" }))
      .mockResolvedValueOnce(row);
    show();
    expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't load your gift.");
    expect(screen.queryByText("₹750.00")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("₹750.00")).toBeVisible();
    expect(gift).toHaveBeenCalledTimes(2);
  });

  it("a refused refetch hides retained gift details and payment actions, with no Retry for the refusal", async () => {
    const refused = new StructuredApiError(403, { code: "permission_denied", detail: "Private" });
    gift.mockResolvedValueOnce(row).mockRejectedValueOnce(refused).mockResolvedValueOnce(row);
    const client = show();
    expect(await screen.findByText("₹750.00")).toBeVisible();
    expect(screen.getByRole("button", { name: "Pay online" })).toBeEnabled();
    await act(async () => { await client.refetchQueries({ queryKey: donationKeys.gift("signed"), exact: true }); });
    expect(client.getQueryState(donationKeys.gift("signed"))?.error).toBe(refused);
    expect(client.getQueryData(donationKeys.gift("signed"))).toEqual(row);
    expect({ status: refused.status, code: refused.code }).toEqual({ status: 403, code: "permission_denied" });
    expect(await screen.findByRole("alert")).toHaveTextContent("Private");
    expect(screen.queryByText("₹750.00")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Pay online" })).not.toBeInTheDocument();
    expect(checkout).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
    expect(gift).toHaveBeenCalledTimes(2);
    for (const call of [1, 2]) expect(gift).toHaveBeenNthCalledWith(call, "signed");
    // Recovery without the (withheld) Retry: a later successful read restores the details and an enabled "Pay online".
    await act(async () => { await client.refetchQueries({ queryKey: donationKeys.gift("signed"), exact: true }); });
    expect(await screen.findByText("₹750.00")).toBeVisible();
    expect(screen.getByRole("button", { name: "Pay online" })).toBeEnabled();
    expect(gift).toHaveBeenCalledTimes(3);
    expect(gift).toHaveBeenNthCalledWith(3, "signed");
  });

  it("with the rail off the gift remains readable and no checkout action is offered", async () => {
    gift.mockResolvedValue({ ...row, online_available: false });
    show();
    expect(await screen.findByText("₹750.00")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Pay online" })).not.toBeInTheDocument();
    expect(checkout).not.toHaveBeenCalled();
  });

  it("an in-flight checkout disables a second submit and a settled response refreshes the cached gift", async () => {
    let resolve!: (value: GiftStatus) => void;
    gift.mockResolvedValue(row);
    checkout.mockReturnValue(new Promise<GiftStatus>(done => { resolve = done; }));
    show();
    fireEvent.click(await screen.findByRole("button", { name: "Pay online" }));
    const pending = await screen.findByRole("button", { name: "Opening checkout…" });
    expect(pending).toBeDisabled();
    fireEvent.click(pending);
    expect(checkout).toHaveBeenCalledTimes(1);
    resolve({ ...row, status: "paid", payment_status: "paid_offline" });
    expect(await screen.findByText("Thank you. Your gift has been received.")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Pay online" })).not.toBeInTheDocument();
    expect(gift).toHaveBeenCalledTimes(1);
  });
});
