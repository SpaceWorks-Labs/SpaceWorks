import { describe, expect, it } from "vitest";
import { latestDecision, reimbursementStateLabel, screeningRecommendationLabel, travelCategoryLabel } from "./labels";

describe("reimbursement wording", () => {
  it.each([
    ["draft", "Draft"], ["requested", "Requested"], ["waitlisted", "Waitlisted"], ["awarded", "Awarded"], ["declined", "Declined"], ["withdrawn", "Withdrawn"],
    ["expired", "Expired"], ["offered", "Offered"], ["accepted", "Accepted"], ["forfeited", "Forfeited"], ["closed", "Closed"], ["open", "Open"],
    ["submitted", "Submitted"], ["under_review", "Under review"], ["returned_for_info", "More information needed"], ["approved", "Approved"],
    ["partially_approved", "Partly approved"], ["rejected", "Rejected"], ["paid", "Paid"],
  ])("state %s reads %s", (state, label) => expect(reimbursementStateLabel(state)).toBe(label));
  it("falls back to spaced words for an unknown state", () => expect(reimbursementStateLabel("on_hold_again")).toBe("on hold again"));

  it.each([["rail", "Rail"], ["air", "Air"], ["bus", "Bus"], ["ground_transport", "Ground transport"], ["lodging", "Lodging"]])(
    "category %s reads %s", (category, label) => expect(travelCategoryLabel(category)).toBe(label));
  it("falls back for an unknown category", () => expect(travelCategoryLabel("ferry_boat")).toBe("ferry boat"));

  it.each([["approve", "Approve"], ["partial", "Partially approve"], ["reject", "Reject"], ["request_info", "Request more information"]])(
    "recommendation %s reads %s", (value, label) => expect(screeningRecommendationLabel(value)).toBe(label));
  it("falls back for an unknown recommendation", () => expect(screeningRecommendationLabel("send_back")).toBe("send back"));
});

describe("latestDecision", () => {
  const claim = (decisions: { sequence: number; reason?: string }[]) => ({ decisions }) as never;
  it("is null for no claim, no decisions or an empty list", () => {
    expect(latestDecision(null)).toBeNull();
    expect(latestDecision(undefined)).toBeNull();
    expect(latestDecision({} as never)).toBeNull();
    expect(latestDecision(claim([]))).toBeNull();
  });
  it("picks the highest sequence regardless of order", () => {
    expect(latestDecision(claim([{ sequence: 2, reason: "b" }, { sequence: 5, reason: "e" }, { sequence: 3, reason: "c" }]))).toEqual({ sequence: 5, reason: "e" });
  });
  it("returns the only decision", () => expect(latestDecision(claim([{ sequence: 1, reason: "a" }]))).toEqual({ sequence: 1, reason: "a" }));
});
