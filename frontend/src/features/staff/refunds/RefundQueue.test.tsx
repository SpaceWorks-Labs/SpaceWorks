import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../../lib/api";
import { RefundQueue } from "./RefundQueue";
import { suggestedAmount } from "./RefundDecisionDialog";
import { policySentence } from "./RefundCaseRow";
import { caseErrorMessage, formatWindow, type RefundCase } from "./refundsApi";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api");
  return { ...actual, staffRequest };
});

const sampleCase: RefundCase = {
  id: 12, kind: "due", area: "events", reason_code: "event_cancelled", member_reason: "Moving away",
  due_amount: "20.00", policy_snapshot: { rule: "event_cancelled_full" }, status: "open", approved_amount: null,
  decision_note: "", refund: null, refundable_balance: "20.00", needs_finance_approval: false,
  created_at: "2026-10-20T10:00:00Z", decided_at: null,
  payment: { id: 3, subject_type: "event_registration", subject_label: "Laser basics", status: "paid_offline",
    amount: "20.00", currency: "usd", member_name: "Asha Rao" },
};

function renderQueue(canDecide = true) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}>
    <RefundQueue makerspaceId={7} makerspaceName="North Lab" canDecide={canDecide} canEditPolicy={false} />
  </QueryClientProvider>);
}

beforeEach(() => {
  staffRequest.mockReset();
  staffRequest.mockImplementation((path: string) => path.includes("/refund-cases?")
    ? Promise.resolve({ count: 1, next: null, previous: null, results: [sampleCase] })
    : Promise.resolve({ ...sampleCase, status: "approved" }));
});

describe("RefundQueue", () => {
  it("lists open cases and approves a cash refund with its receipt", async () => {
    renderQueue();
    fireEvent.click(await screen.findByRole("button", { name: /Asha Rao · Laser basics/ }));
    expect(screen.getByText(/full amount is owed/)).toBeInTheDocument();
    expect(screen.getByText(/“Moving away”/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Refund reference (optional)"), { target: { value: "slip-9" } });
    fireEvent.click(screen.getByRole("button", { name: /Record \$20\.00 returned/ }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/7/refund-cases/12/approve",
      expect.objectContaining({ method: "POST" })));
    const body = JSON.parse(staffRequest.mock.calls.find(([path]) => String(path).endsWith("/approve"))![1].body);
    expect(body).toMatchObject({ amount: "20.00", receipt: { method: "cash", reference: "slip-9" } });
  });

  it("declining needs a note the member will see", async () => {
    renderQueue();
    fireEvent.click(await screen.findByRole("button", { name: /Asha Rao/ }));
    fireEvent.click(screen.getByRole("radio", { name: "Decline" }));
    fireEvent.click(screen.getByRole("button", { name: "Decline refund" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/They will see this note/);
    fireEvent.change(screen.getByLabelText("Note to the member"), { target: { value: "Outside the window" } });
    fireEvent.click(screen.getByRole("button", { name: "Decline refund" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/7/refund-cases/12/decline",
      { method: "POST", body: JSON.stringify({ note: "Outside the window" }) }));
  });

  it("finance readers see cases but cannot open a decision", async () => {
    renderQueue(false);
    expect(await screen.findByText("Asha Rao · Laser basics")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Asha Rao/ })).not.toBeInTheDocument();
  });

  it("explains figures and errors in plain words", () => {
    expect(suggestedAmount({ due_amount: "0.00", refundable_balance: "15.50" })).toBe("15.50");
    expect(suggestedAmount({ due_amount: "30.00", refundable_balance: "15.50" })).toBe("15.50");
    expect(policySentence({ rule: "policy", band: "partial", partial_percent: 50, minutes_before_start: 1500,
      fee_applied: "2.00" })).toBe("Cancelled 25 hours before the start: the policy refunds 50%, minus a 2.00 cancellation fee.");
    expect(policySentence({ rule: "policy", area: "membership", band: "pro_rata", fee_applied: "0.00" }))
      .toBe("Membership term cancelled: the policy refunds the unused part of the term.");
    expect(policySentence({ rule: "staff_cancelled_full" })).toMatch(/Staff cancelled this booking/);
    expect(formatWindow(2880)).toBe("2 days before");
    expect(formatWindow(0)).toBe("until the start");
    expect(caseErrorMessage(new StructuredApiError(409, { detail: "x", code: "refund_rail_unavailable" }))).toMatch(/Decline the case/);
  });
});
