import { describe, expect, it } from "vitest";

import { isRetryable as fromBarrel } from "../api";
import { apiError, isRetryable, StructuredApiError } from "./errors";

// Decision 588: Retry only where a retry can succeed - a 5xx, a 429 or no response at all.
describe("isRetryable", () => {
  it("retries every server-side failure and a rate limit", () => {
    for (const status of [500, 502, 503, 504, 599, 429]) {
      expect(isRetryable(new StructuredApiError(status, { detail: "Outage." })), String(status)).toBe(true);
    }
    expect(isRetryable(apiError(429, { code: "ip_blocked" }, new Headers({ "Retry-After": "30" })))).toBe(true);
  });

  it("retries a request that got no response (network failure, abort, parse failure)", () => {
    expect(isRetryable(new TypeError("Failed to fetch"))).toBe(true);
    expect(isRetryable(new DOMException("The operation was aborted.", "AbortError"))).toBe(true);
    expect(isRetryable(new Error("Unexpected end of JSON input"))).toBe(true);
    expect(isRetryable("offline")).toBe(true);
  });

  it("never retries a refusal: it would be answered the same way again", () => {
    for (const [status, code] of [
      [400, "invalid"], [401, "not_authenticated"], [403, "permission_denied"], [404, "not_found"],
      [404, "module_disabled"], [404, "feature_disabled"], [409, "idempotency_conflict"], [410, "gone"],
      [413, "too_large"], [422, "invalid"], [423, "space_read_only"], [499, "client_closed"],
    ] as const) {
      expect(isRetryable(new StructuredApiError(status, { code, detail: "Refused." })), `${status} ${code}`).toBe(false);
    }
  });

  it("is the same helper through the lib/api barrel", () => {
    expect(fromBarrel).toBe(isRetryable);
  });
});
