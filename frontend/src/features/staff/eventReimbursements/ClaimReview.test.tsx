import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { ClaimReview } from "./ClaimReview";
import { decisionBody } from "./ClaimDecision";
import type { ClaimReviewDetail } from "./types";
const mocked = vi.hoisted(() => ({ row: {} as ClaimReviewDetail, mutate: vi.fn() }));
vi.mock("./api", () => ({ reimbursementAdminPath: () => "/admin/events/41/reimbursements/", useClaimReview: () => ({ data: mocked.row, isPending: false }),
  useClaimReviewCommand: () => ({ mutate: mocked.mutate, isPending: false, isSuccess: false, error: null }) }));
const scope = { actorId: 1, makerspaceId: 2, eventId: 41 };
function row(actions: string[]): ClaimReviewDetail {
  return { id: 9, uuid: "claim", version: 3, state: "submitted", owner_label: "Maker", currency: "INR", claimed_minor: 175000,
    due_at: "2026-12-10T00:00:00Z", due_revision: 1, allowed_actions: actions, claim_revision_id: 7, decision_sequence: 0,
    obligation_version: null, eligibility_revision: 2, attendance_revision: 2, registration_id: 101, accepted_cap_minor: 150000,
    pool_version: 4,
    lines: [{ line_uuid: "rail-line", category: "rail", original_amount_minor: 175000, original_currency: "INR", converted_minor: 175000,
      receipt_present: true, duplicate_receipt: false, receipt_asset_id: 91, receipt_use_version: 1 }], attendance_eligible: true,
    recommendations: [], decision_reason: "", appeal_statement: null };
}
afterEach(() => { mocked.mutate.mockReset(); });
describe("reviewer and finance decision boundaries", () => {
  it("reviewer can recommend without receipt bytes or a final approval control", () => {
    mocked.row = row(["claim_recommend"]);
    render(<ClaimReview scope={scope} claimId={9} onReceipt={vi.fn()} />);
    expect(screen.queryByText("Final finance decision")).toBeNull();
    expect(screen.queryByRole("button", { name: /open receipt/i })).toBeNull();
    fireEvent.change(screen.getByLabelText("Reason"), { target: { value: "information_required" } });
    fireEvent.change(screen.getByLabelText("Screening note"), { target: { value: "Please review." } });
    fireEvent.submit(screen.getByRole("button", { name: "Submit recommendation" }).closest("form")!);
    expect(mocked.mutate).toHaveBeenCalledWith({ path: "/admin/events/41/reimbursements/claims/9/review/", body: {
      expected_version: 3, claim_revision_id: 7, mode: "recommend", recommendation: "request_info", reason_code: "information_required", note: "Please review.",
    } });
  });
  it("shows finance entry points only when returned by the server", () => {
    mocked.row = row(["claim_decide", "receipt_read", "attendance_attest", "receipt_override", "claim_extend"]);
    render(<ClaimReview scope={scope} claimId={9} onReceipt={vi.fn()} />);
    expect(screen.getByText("Final finance decision")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /open receipt/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Confirm finance decision" })).toBeDisabled();
    expect(screen.queryByText("Screening recommendation")).toBeNull();
  });
  it("pins current pool, decision, obligation and eligibility versions and enforces the accepted cap", () => {
    const detail = row(["claim_decide"]);
    const body = decisionBody(detail, "partially_approved", [{ line_uuid: "rail-line", approved_minor: 150000, reason_code: "policy_cap" }], "policy_cap", "Bounded to accepted cap.", "");
    expect(body).toMatchObject({ mode: "decide", expected_version: 3, claim_revision_id: 7, expected_pool_version: 4,
      expected_decision_sequence: 0, expected_obligation_version: null, eligibility_revision: 2 });
    expect(() => decisionBody(detail, "approved", [{ line_uuid: "rail-line", approved_minor: 175000, reason_code: "full" }], "full", "Full", "")).toThrow(/accepted cap/);
  });
});
