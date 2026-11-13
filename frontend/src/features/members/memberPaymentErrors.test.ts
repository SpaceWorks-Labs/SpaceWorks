import { describe, expect, it } from "vitest";

import { StructuredApiError } from "../../lib/api";
import { memberPaymentErrorText } from "./memberPaymentErrors";

const refusal = (status: number, code?: string, detail = "Server words") =>
  new StructuredApiError(status, code ? { detail, code } : { detail });

describe("memberPaymentErrorText", () => {
  it.each([
    [503, "payments_unavailable", /Pay at the space/],
    [409, "payment_rail_conflict", /being paid in the app/],
    [409, "payment_settlement_pending", /Wait for them to confirm it before paying again/],
    [409, "payment_terminal", /no longer waiting for payment/],
    [409, "claim_exists", /already told the space/],
    [409, "claim_reference_invalid", /6-35 character/],
    [404, "feature_disabled", /Pay at the space or contact them/],
    [404, "pay_link_invalid", /Ask the space for a new link/],
  ])("turns a %i %s refusal into the payer's next step", (status, code, copy) => {
    expect(memberPaymentErrorText(refusal(status, code))).toMatch(copy);
  });

  it("treats a bare 404 as a charge that is no longer payable and a 429 as a wait", () => {
    expect(memberPaymentErrorText(refusal(404))).toMatch(/Refresh to see its latest status/);
    expect(memberPaymentErrorText(refusal(429))).toMatch(/Wait a minute/);
  });

  it("falls back to the server's message, a network hint, or nothing", () => {
    expect(memberPaymentErrorText(refusal(400, "other_code", "Exact server reason"))).toBe("Exact server reason");
    expect(memberPaymentErrorText(new TypeError("Failed to fetch"))).toMatch(/Check your connection/);
    expect(memberPaymentErrorText(null)).toBe("");
  });
});
