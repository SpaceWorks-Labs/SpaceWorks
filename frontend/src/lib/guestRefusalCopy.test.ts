import { describe, expect, it } from "vitest";

import { StructuredApiError } from "./api/errors";
import { eligibilityMessage } from "./eligibilityCopy";
import { guestRefusalMessage } from "./guestRefusalCopy";

const CODES = [
  "guest_not_eligible", "already_member", "pass_exists_today", "visit_cap_reached", "sponsor_not_member", "sponsor_tenure",
  "sponsor_presence_required", "sponsor_limit", "charges_off", "product_unavailable", "day_pass_sold_out", "pass_not_live",
  "no_waiver_published", "guest_pass_no_borrow", "guest_pass_on_site_only", "guest_pass_required", "guest_pass_deposit_required",
  "account_not_in_space", "guest_pass_no_machines", "guest_pass_supervised_only", "guest_pass_supervised_session",
  "guest_pass_machine_access_required", "minor_not_admitted", "minor_below_minimum_age", "guardian_terms_missing",
  "guardian_consent_required", "guardian_consent_expired", "guardian_presence_required", "minor_borrowing_not_allowed",
  "minor_machines_not_allowed",
];

describe("guest, day-pass and minors refusal copy (decision 223)", () => {
  it("has plain words for every refusal code the backend lanes listed", () => {
    for (const code of CODES) expect(guestRefusalMessage(code), code).toMatch(/\w/);
    expect(guestRefusalMessage("something_else")).toBeNull();
  });

  it("reaches every surface through eligibilityMessage, including DRF's list-shaped code", () => {
    expect(eligibilityMessage(new StructuredApiError(403, { code: "guest_pass_no_borrow" }))).toMatch(/don't include borrowing/);
    expect(eligibilityMessage(new StructuredApiError(400, { code: ["minor_machines_not_allowed"] }))).toMatch(/can't use machines/);
    expect(eligibilityMessage(new StructuredApiError(403, { code: "waiver_acceptance_required" }))).toMatch(/waiver/);
  });
});
