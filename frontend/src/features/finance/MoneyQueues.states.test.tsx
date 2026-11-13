import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../lib/api/errors";
import { MoneyQueues } from "./MoneyQueues";

// MOD-3 flow audit (payments ledger, staff queues): empty, two-person rule, refusal, reject-with-note.
const api = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", async (original) => ({ ...(await original<typeof import("../../lib/api")>()), staffRequest: api.staffRequest }));

const claim = { id: 5, payment_id: 31, subject_label: "Laser hour", method: "upi", reference: "UTR123", paid_on: "2026-11-10", amount: "250.00",
  currency: "inr", status: "submitted", decision_note: "", decided_at: null, created_at: "2026-11-10T10:00:00Z", via_pay_link: false };
const settlement = (over = {}) => ({ id: 8, payment_id: 32, subject_label: "Membership", method: "cash", reference: "", received_at: "2026-11-09T09:00:00Z", amount: "1200.00",
  currency: "inr", status: "awaiting_confirmation", decision_note: "", created_at: "2026-11-09T09:00:00Z", decided_at: null, proposed_by_me: false, from_claim: false, ...over });
const page = (results: unknown[]) => ({ count: results.length, next: null, previous: null, results });

function show(claimsOn = true) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><MoneyQueues makerspaceId={5} claimsOn={claimsOn} /></QueryClientProvider>);
}
const serve = (claims: unknown[], settlements: unknown[], decide?: (path: string) => unknown) => api.staffRequest.mockImplementation(async (path: string) => {
  if (decide && /\/(confirm|reject)$/.test(path)) return decide(path);
  if (path.includes("/paid-claims")) return page(claims);
  if (path.includes("/settlements")) return page(settlements);
  throw new Error(`unexpected ${path}`);
});

beforeEach(() => { api.staffRequest.mockReset(); });

describe("MoneyQueues", () => {
  it("shows both empty states", async () => {
    serve([], []);
    show();
    expect(await screen.findByText("No claims waiting.")).toBeInTheDocument();
    expect(await screen.findByText("Nothing waiting.")).toBeInTheDocument();
  });

  it("with claims switched off never asks for claims and hides that section", async () => {
    serve([], []);
    show(false);
    expect(await screen.findByText("Nothing waiting.")).toBeInTheDocument();
    expect(screen.queryByText("Payers say they paid")).not.toBeInTheDocument();
    expect(api.staffRequest.mock.calls.some(([path]) => String(path).includes("/paid-claims"))).toBe(false);
  });

  it("the recorder sees 'You recorded this' and no confirm/reject buttons (two-person rule); another person can confirm", async () => {
    serve([], [settlement({ id: 8, proposed_by_me: true }), settlement({ id: 9, proposed_by_me: false, subject_label: "Day pass" })], () => settlement({ id: 9, status: "confirmed" }));
    show();
    expect(await screen.findByText("You recorded this")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Confirm" })).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Confirm" }));
    await waitFor(() => expect(api.staffRequest.mock.calls.some(([path]) => String(path).endsWith("/settlements/9/confirm"))).toBe(true));
    expect(await screen.findByText("Settlement confirmed.")).toBeInTheDocument();
  });

  it("a refused confirmation shows the access message and keeps the claim listed", async () => {
    serve([claim], [], () => { throw new StructuredApiError(403, { detail: "no" }); });
    show();
    fireEvent.click(await screen.findByRole("button", { name: "Confirm payment" }));
    expect(await screen.findByText("You don't have access to this money.")).toBeInTheDocument();
    expect(screen.getByText(/UTR123/)).toBeInTheDocument();
  });

  it("'Not received' asks for a note first, then posts the rejection with that note", async () => {
    serve([claim], [], () => ({ ...claim, status: "rejected" }));
    show();
    fireEvent.click(await screen.findByRole("button", { name: "Not received" }));
    fireEvent.change(await screen.findByRole("textbox"), { target: { value: "No transfer seen" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Reject" }).pop()!);
    await waitFor(() => {
      const call = api.staffRequest.mock.calls.find(([path]) => String(path).endsWith("/paid-claims/5/reject"));
      expect(call).toBeTruthy();
      expect(JSON.parse(String(call![1].body))).toEqual({ note: "No transfer seen" });
    });
    expect(await screen.findByText("Claim rejected.")).toBeInTheDocument();
  });
});
