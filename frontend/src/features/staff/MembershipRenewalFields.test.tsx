import { describe, expect, it } from "vitest";
import { emptyRenewal, renewalInput, validateRenewal } from "./MembershipRenewalFields";

describe("Renewal policy fields", () => {
  it("keeps opt-in off and normalizes configured local-day reminders", () => {
    expect(renewalInput(emptyRenewal)).toEqual({ auto_renew: false, renewal_open_days: 7, renewal_grace_days: 0, renewal_retries: 0, reminder_days_before: [1, 7, 14], reminder_days_after: [] });
    expect(renewalInput({ ...emptyRenewal, reminder_days_after: "7, 1, 7" }).reminder_days_after).toEqual([1, 7]);
  });
  it("bounds retries, grace and each reminder offset", () => {
    expect(validateRenewal({ ...emptyRenewal, renewal_retries: "4" })).toBe("Enter a whole number between 0 and 3 for renewal timing.");
    expect(validateRenewal({ ...emptyRenewal, renewal_grace_days: "-1" })).toBe("Enter a whole number between 0 and 365 for renewal timing.");
    expect(validateRenewal({ ...emptyRenewal, reminder_days_before: "1,366" })).toBe("Use up to ten reminder day offsets between 1 and 365, separated by commas.");
    expect(validateRenewal(emptyRenewal)).toBeNull();
  });
});
