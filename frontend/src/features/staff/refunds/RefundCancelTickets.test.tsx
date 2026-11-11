import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { StructuredApiError } from "../../../lib/api";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async (original) => ({ ...await original<object>(), staffRequest }));

import { RefundDecisionDialog } from "./RefundDecisionDialog";
import { caseErrorMessage, type RefundCase } from "./refundsApi";

const ticketCase: RefundCase = {
  id: 21, kind: "due", area: "events", reason_code: "member_request", member_reason: "", due_amount: "30.00",
  policy_snapshot: { rule: "manual" }, status: "open", approved_amount: null, decision_note: "", refund: null,
  refundable_balance: "30.00", needs_finance_approval: false, created_at: "2026-11-01T10:00:00Z", decided_at: null,
  payment: { id: 5, subject_type: "event_order", subject_label: "Robot night", status: "paid_online", amount: "30.00", currency: "usd", member_name: "Ravi" },
};

function mount(refundCase: RefundCase, cancelTicketsAvailable: boolean) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}>
    <RefundDecisionDialog makerspaceId={7} refundCase={refundCase} onClose={vi.fn()} cancelTicketsAvailable={cancelTicketsAvailable} />
  </QueryClientProvider>);
}
const approveBody = () => JSON.parse(staffRequest.mock.calls.find(([path]) => String(path).endsWith("/approve"))![1].body);

beforeEach(() => { staffRequest.mockReset(); staffRequest.mockResolvedValue({ ...ticketCase, status: "approved" }); });

describe("refund approval can cancel the tickets (parity C18)", () => {
  it("sends cancel_tickets only when ticked on an event ticket charge", async () => {
    mount(ticketCase, true);
    const tick = screen.getByRole("checkbox", { name: "Also cancel the tickets this payment bought" });
    expect(tick).not.toBeChecked();
    fireEvent.click(tick);
    expect(screen.getByText(/The places are freed/)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: /Refund \$30\.00/ }));
    await waitFor(() => expect(approveBody()).toMatchObject({ amount: "30.00", cancel_tickets: true }));
  });

  it("leaves the field out when the tick stays clear", async () => {
    mount(ticketCase, true);
    fireEvent.click(screen.getByRole("button", { name: /Refund \$30\.00/ }));
    await waitFor(() => expect(approveBody()).not.toHaveProperty("cancel_tickets"));
  });

  it("hides the tick when the switch is off or the charge is not an event ticket", () => {
    const { unmount } = mount(ticketCase, false);
    expect(screen.queryByRole("checkbox", { name: /cancel the tickets/ })).toBeNull();
    unmount();
    mount({ ...ticketCase, area: "bookings", payment: { ...ticketCase.payment, subject_type: "booking" } }, true);
    expect(screen.queryByRole("checkbox", { name: /cancel the tickets/ })).toBeNull();
  });

  it("explains the two refusal codes", () => {
    expect(caseErrorMessage(new StructuredApiError(400, { code: "refund_cancel_tickets_unavailable", detail: "x" }))).toMatch(/turned off/);
    expect(caseErrorMessage(new StructuredApiError(400, { code: "refund_cancel_tickets_not_event", detail: "x" }))).toMatch(/Only a refund on an event ticket/);
  });
});
