import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { Reimbursements } from "./Reimbursements";
import type { ReimbursementOverview } from "./types";

const mocked = vi.hoisted(() => ({ data: undefined as unknown, mutate: vi.fn() }));
vi.mock("./api", () => ({ reimbursementPath: () => "/member/makerspaces/2/events/41/reimbursement/",
  useReimbursement: () => ({ data: mocked.data, isPending: false, error: null, refetch: vi.fn() }),
  useApplicantCommand: () => ({ mutate: mocked.mutate, isPending: false, error: null }) }));
vi.mock("../stagedForms/useNow", () => ({ useNow: () => Date.parse("2026-12-01T00:00:00Z") }));

const scope = { actorId: 1, makerspaceId: 2, eventId: 41 };
// The server's MemberSummary (projections.member_summary), not a client-invented shape.
function summary(over: Partial<ReimbursementOverview>): ReimbursementOverview {
  return { available: true, allowed_actions: [], programme: { initialized: true, currency: "INR", allowed_categories: ["rail"],
    claim_due_at: "2026-12-20T00:00:00Z", category_limits: { rail: 150000 } }, request_context: null, request: null, award: null, claim: null, ...over };
}
const handlers = () => ({ onRequest: vi.fn(), onClaim: vi.fn(), onAppeal: vi.fn(), onPayout: vi.fn() });
afterEach(() => mocked.mutate.mockReset());

describe("member travel support page", () => {
  it("starts a request from the server's create_request action", () => {
    mocked.data = summary({ allowed_actions: ["create_request", "submit_request"] });
    render(<Reimbursements scope={scope} {...handlers()} />);
    expect(screen.getByText(/Eligible travel: Rail/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Start support request" }));
    expect(mocked.mutate).toHaveBeenCalledWith({ path: "/member/makerspaces/2/events/41/reimbursement/", body: { expected_version: 0 } }, expect.anything());
  });
  it("offers accept and decline for an open award offer", () => {
    mocked.data = summary({ allowed_actions: ["accept_award", "decline_award"],
      request: { id: 1, uuid: "r", version: 2, state: "awarded", estimated_total_minor: 200000, currency: "INR", reason_code: "", reason: "" },
      award: { id: 3, uuid: "a", version: 1, state: "offered", amount_minor: 150000, currency: "INR", award_revision: 1,
        accept_by: "2026-12-05T00:00:00Z", accepted_at: null, reason_code: "", calculation_snapshot: {} } });
    render(<Reimbursements scope={scope} {...handlers()} />);
    expect(screen.getByRole("button", { name: "Accept award" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Decline award" })).toBeInTheDocument();
  });
  it("opens a claim once the award is accepted and shows the payout link and appeal", () => {
    const h = handlers();
    mocked.data = summary({ claim: { id: 9, uuid: "c", version: 4, state: "partially_approved", display_state: "partially_approved",
      current_revision: 2, effective_due_at: "2026-12-20T00:00:00Z", info_due_at: null, appeal_due_at: "2026-12-12T00:00:00Z",
      appeal_used: false, allowed_actions: ["appeal"], decisions: [{ id: 1, sequence: 1, outcome: "partially_approved",
        approved_total_minor: 100000, currency: "INR", reason_code: "policy_cap", reason: "Capped at the award.", decided_at: "2026-12-02T00:00:00Z" }],
      payout: { id: "ob-1", version: 1, currency: "INR", approved_minor: 100000, effective_paid_minor: 0, remaining_minor: 100000, state: "open" } } });
    render(<Reimbursements scope={scope} {...h} />);
    expect(screen.getByText("Capped at the award.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Appeal decision" }));
    fireEvent.click(screen.getByRole("button", { name: "Payee details and payment history" }));
    expect(h.onAppeal).toHaveBeenCalled();
    expect(h.onPayout).toHaveBeenCalledWith("ob-1");
  });
});
