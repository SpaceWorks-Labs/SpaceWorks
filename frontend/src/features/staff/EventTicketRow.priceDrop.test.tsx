import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"), staffRequest: request }));

import { EventTicketRow } from "./EventTicketRow";
import { RefundCaseRow, policySentence } from "./refunds/RefundCaseRow";
import { REASON_LABELS, type RefundCase } from "./refunds/refundsApi";

const sold = { id: 5, name: "Standard", amount: "20.00", audience: "public" as const, capacity: 40, sales_start_at: null,
  sales_end_at: null, is_active: true, registration_count: 2 };
const report = { count: 1, truncated: false, totals: [{ currency: "usd", difference: "5.00" }], items: [{
  area: "events", item_type: "registration", item_id: 9, label: "Paid workshop", starts_at: null, payment_id: 3,
  currency: "usd", paid: "20.00", before: "20.00", after: "15.00", difference: "5.00", case_id: null }] };

function show(features: string[]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  // #184 G5 (0acf6df0): a ticket shows a price only where event charges are tracked.
  client.setQueryData(["staff", "makerspaces"], [{ id: 1, enabled_modules: ["events"], enabled_features: ["charges.enabled", "charges.events", ...features] }]);
  render(<QueryClientProvider client={client}><ul><EventTicketRow row={sold} eventId={4} disabled={false} /></ul></QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Edit Standard" }));
  return screen.getByRole("form", { name: "Edit Standard" });
}

beforeEach(() => {
  request.mockReset();
  request.mockImplementation((path: string, options?: RequestInit) => {
    if (path.includes("price_drop_preview=1")) return Promise.resolve({ price_drop: report });
    if (options?.method === "PATCH") return Promise.resolve({ ...sold, ...JSON.parse(String(options.body)) });
    return Promise.resolve({ count: 0, next: null, previous: null, results: [] });
  });
});

describe("lowering a sold ticket (#163A)", () => {
  it("keeps a sold ticket's price frozen while price-drop refunds are off", () => {
    const form = show([]);
    expect(within(form).getByLabelText("Price")).toBeDisabled();
  });

  it("lets a sold fixed-price ticket get cheaper, previews the refunds and saves only on confirm", async () => {
    const form = show(["charges.price_drop_refunds"]);
    const price = within(form).getByLabelText("Price");
    expect(price).toBeEnabled();
    expect(price).toHaveAttribute("max", "20.00");
    fireEvent.change(price, { target: { value: "15.00" } });
    fireEvent.click(within(form).getByRole("button", { name: "Save ticket type" }));
    expect(await screen.findByText("Lower this price?")).toBeVisible();
    expect(request).toHaveBeenCalledWith("/admin/event-ticket-types/5/?price_drop_preview=1",
      { method: "PATCH", body: JSON.stringify({ amount: "15.00" }) });
    expect(request).not.toHaveBeenCalledWith("/admin/event-ticket-types/5/", expect.anything());
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Save and open refunds" })); });
    await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/event-ticket-types/5/",
      { method: "PATCH", body: JSON.stringify({ amount: "15.00" }) }));
  });

  it("saves nothing when staff back out of the preview", async () => {
    const form = show(["charges.price_drop_refunds"]);
    fireEvent.change(within(form).getByLabelText("Price"), { target: { value: "15.00" } });
    fireEvent.click(within(form).getByRole("button", { name: "Save ticket type" }));
    await screen.findByText("Lower this price?");
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Keep editing" })); });
    expect(request).not.toHaveBeenCalledWith("/admin/event-ticket-types/5/", expect.anything());
  });
});

describe("refund queue wording for L24 cases", () => {
  it("names the three reasons and explains each difference", () => {
    expect(REASON_LABELS.price_drop).toBe("Price lowered after payment");
    expect(REASON_LABELS.job_cancelled).toBe("Prepaid job cancelled before it started");
    expect(REASON_LABELS.quote_difference).toBe("Job cost less than its prepaid quote");
    expect(policySentence({ shares: [{ source: "price_drop" }] })).toMatch(/price was lowered/);
    expect(policySentence({ shares: [{ source: "quote_difference" }] })).toMatch(/cost less than its quote/);
    expect(policySentence({ shares: [{ source: "job_cancelled" }] })).toMatch(/cancelled this prepaid job/);
  });

  it("marks an open difference case as one the Space Manager or finance approves", () => {
    const row = { id: 1, kind: "due", area: "bookings", reason_code: "price_drop", member_reason: "", due_amount: "10.00",
      policy_snapshot: { shares: [{ source: "price_drop" }] }, status: "open", approved_amount: null, decision_note: "",
      refund: null, refundable_balance: "30.00", needs_finance_approval: true, created_at: new Date().toISOString(),
      decided_at: null, payment: { id: 3, subject_type: "booking", subject_label: "Laser room", status: "paid_offline",
        amount: "30.00", currency: "usd", member_name: "Asha" } } as unknown as RefundCase;
    render(<RefundCaseRow row={row} />);
    expect(screen.getByText("Space Manager or finance approves")).toBeVisible();
    expect(screen.getByText("Price lowered after payment")).toBeVisible();
  });
});
