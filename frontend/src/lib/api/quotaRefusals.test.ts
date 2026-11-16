import { describe, expect, it } from "vitest";
import { quotaMessage, StructuredApiError } from "./errors";

describe("quota and platform-limit refusals (decisions 281, 284)", () => {
  it.each([
    ["event_quota_reached", /Existing events are not affected/],
    ["booking_quota_reached", /Existing bookings are not affected/],
    ["payment_quota_reached", /Charges that already exist can still be paid/],
    ["platform_rail_limit_reached", /can still be paid at the desk/],
    ["shop_orders_monthly_quota_reached", /existing charges can still be paid/],
  ])("explains a 409 %s in plain words, on message and detail", (code, text) => {
    const error = new StructuredApiError(409, { detail: "Raw server text.", code, limit: 5 });
    expect(error.message).toMatch(text);
    expect(error.detail).toMatch(text);
    expect(error.code).toBe(code);
  });

  it("reads the DRF list shape of the wallet refusal (400)", () => {
    const error = new StructuredApiError(400, { platform: ["Limit reached."], code: ["platform_wallet_limit_reached"] });
    expect(error.message).toMatch(/Your card still works in the app/);
  });

  it("leaves unrelated codes and statuses alone", () => {
    expect(quotaMessage("job_limit_reached")).toBe("");
    expect(new StructuredApiError(409, { detail: "Conflict.", code: "payment_terminal" }).message).toBe("Conflict.");
    expect(new StructuredApiError(500, { detail: "Boom.", code: "event_quota_reached" }).message).toBe("Boom.");
  });
});
