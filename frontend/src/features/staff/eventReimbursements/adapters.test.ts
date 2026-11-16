import { describe, expect, it } from "vitest";
import { toClaimReview, toClaimRow, toProgramme, toRequestRow } from "./adapters";
import { decisionBody } from "./ClaimDecision";

// Shapes exactly as the server's projections send them (projections.py + staff_projection.py).
const rawRequest = { id: 4, version: 2, state: "requested", currency: "INR", estimated_total_minor: 250000, kind: "participant",
  category_estimates: [{ category: "rail" as const }, { category: "lodging" as const }], owner_label: "Asha", allowed_actions: ["decide"],
  tiers: [{ key: "near", label: "near", amount_minor: 100000 }], budget: { pool_id: 1, pool_version: 7, available_minor: 900000 }, award: null };
const rawClaim = { id: 9, uuid: "c-1", version: 3, state: "submitted", display_state: "submitted", owner_label: "Asha", currency: "KWD",
  claimed_minor: 12345, effective_due_at: "2026-12-10T00:00:00Z", info_due_at: null, due_revision: 1, current_revision: 11,
  allowed_actions: ["decide", "attendance_attest", "receipt_override"], payout: { version: 5 }, accepted_cap_minor: 20000,
  pool_version: 8, decision_sequence: 1, decision_reason: "", registration_id: 77, attendance_revision: 3, eligibility_revision: 3,
  attendance_eligible: true, recommendations: [], appeal_statement: null,
  review_lines: [{ line_uuid: "l-1", category: "rail" as const, original_amount_minor: 12345, original_currency: "KWD", converted_minor: 12345,
    receipt_present: true, duplicate_receipt: false, receipt_use_version: 1, receipt_asset_id: 50 }] };

describe("reimbursement read adapters", () => {
  it("maps a screening request row onto the console model", () => {
    const row = toRequestRow(rawRequest);
    expect(row).toMatchObject({ owner_label: "Asha", categories: ["rail", "lodging"], allowed_actions: ["request_decide"],
      expected_award_version: null, budget: { pool_version: 7 } });
  });
  it("pins every version a finance decision checks from the server", () => {
    const review = toClaimReview(rawClaim);
    expect(review).toMatchObject({ claim_revision_id: 11, decision_sequence: 1, obligation_version: 5, eligibility_revision: 3,
      pool_version: 8, registration_id: 77, accepted_cap_minor: 20000 });
    expect(review.allowed_actions).toEqual(["claim_decide", "attendance_attest", "receipt_override", "receipt_read"]);
    const body = decisionBody(review, "returned_for_info", [{ line_uuid: "l-1", approved_minor: 0, reason_code: "information_required" }],
      "information_required", "Need the receipt.", "2026-12-20T10:00");
    expect(body.line_decisions).toEqual([]);
    expect(body).toMatchObject({ expected_pool_version: 8, expected_obligation_version: 5, eligibility_revision: 3 });
  });
  it("hides the receipt viewer from screeners (no asset ids sent)", () => {
    const review = toClaimReview({ ...rawClaim, allowed_actions: ["recommend"], review_lines: [{ ...rawClaim.review_lines[0], receipt_asset_id: undefined }] });
    expect(review.allowed_actions).toEqual(["claim_recommend"]);
  });
  it("uses the effective or information deadline as the queue due date", () => {
    expect(toClaimRow({ ...rawClaim, info_due_at: "2026-12-12T00:00:00Z" }).due_at).toBe("2026-12-12T00:00:00Z");
  });
  it("builds policy settings and picks the participant pool", () => {
    const programme = toProgramme({ initialized: true, id: 1, version: 2, currency: "INR", finance_policy_revision: 3, enabled: true,
      claim_due_at: "2026-12-15T00:00:00Z", allowed_categories: ["rail"],
      pools: [{ id: 2, version: 1, currency: "INR", audience: "crew", total_minor: 1, available_minor: 1, reserved_minor: 0, committed_minor: 0 },
        { id: 1, version: 4, currency: "INR", audience: "participants", total_minor: 9, available_minor: 9, reserved_minor: 0, committed_minor: 0 }] });
    expect(programme).toMatchObject({ policy_revision: 3, pool: { id: 1, version: 4 }, allowed_actions: ["programme_edit"] });
    expect(programme.settings).toEqual({ enabled: true, claim_due_at: "2026-12-15T00:00:00Z", allowed_categories: ["rail"] });
    expect(toProgramme({ initialized: false }).allowed_actions).toEqual(["programme_initialize"]);
  });
});
