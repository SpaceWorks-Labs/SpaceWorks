import { describe, expect, it } from "vitest";
import { apiError, isSurfaceOff, messageForStatus, NOT_FOUND_MESSAGE, PLAN_LIMIT_MESSAGE, quotaCode, quotaMessage, requestFailedMessage,
  SPACE_READ_ONLY_MESSAGE, SPACE_SUSPENDED_MESSAGE, StructuredApiError } from "./errors";

describe("quotaMessage", () => {
  it.each(["event_quota_reached", "booking_quota_reached", "payment_quota_reached", "platform_rail_limit_reached", "platform_wallet_limit_reached"])(
    "%s has its own message", (code) => {
      const text = quotaMessage(code);
      expect(text.length).toBeGreaterThan(40);
      expect(text).not.toBe(quotaMessage("some_other_quota_reached"));
    });
  it("says what still works for payment limits", () => expect(quotaMessage("payment_quota_reached")).toContain("Charges that already exist can still be paid"));
  it("gives a generic monthly-limit line for any other *_quota_reached or platform_*_limit_reached code", () => {
    const generic = "This space has reached a monthly limit set by the platform operator. Nothing that already exists is affected, and existing charges can still be paid.";
    expect(quotaMessage("machine_quota_reached")).toBe(generic);
    expect(quotaMessage("platform_sms_limit_reached")).toBe(generic);
  });
  it.each(["", "not_found", "platform_x", "x_limit_reached", "quota_reached_x"])("is empty for the unrelated code %j", (code) => expect(quotaMessage(code)).toBe(""));
});

describe("quotaCode", () => {
  it("takes the code argument when it is a quota code", () => expect(quotaCode({}, "event_quota_reached")).toBe("event_quota_reached"));
  it("falls back to the first entry of a DRF-wrapped code list", () => expect(quotaCode({ code: ["booking_quota_reached"] })).toBe("booking_quota_reached"));
  it("is empty for a non-quota code, a non-string code or no code", () => {
    expect(quotaCode({}, "invalid")).toBe("");
    expect(quotaCode({ code: [5] })).toBe("");
    expect(quotaCode({})).toBe("");
  });
});

describe("StructuredApiError messages", () => {
  it("replaces Django's model-naming 404 with plain words", () => {
    expect(new StructuredApiError(404, { detail: "No MakerspaceMembership matches the given query." }).message).toBe(NOT_FOUND_MESSAGE);
    expect(new StructuredApiError(404, { detail: "No Thing matches the given query" }).message).toBe(NOT_FOUND_MESSAGE);
  });
  it("keeps other 404 text and non-404 'No X matches' text as sent", () => {
    expect(new StructuredApiError(404, { detail: "Custom not found" }).message).toBe("Custom not found");
    expect(new StructuredApiError(400, { detail: "No Thing matches the given query." }).message).toBe("No Thing matches the given query.");
  });
  it("explains a read-only or paused space only for a 423 with that code", () => {
    expect(new StructuredApiError(423, { code: "space_read_only", detail: "x" }).message).toBe(SPACE_READ_ONLY_MESSAGE);
    expect(new StructuredApiError(423, { code: "space_suspended", detail: "x" }).message).toBe(SPACE_SUSPENDED_MESSAGE);
    expect(new StructuredApiError(400, { code: "space_read_only", detail: "x" }).message).toBe("x");
  });
  it("explains a quota refusal on 400 and 409 only, including a DRF-wrapped code", () => {
    expect(new StructuredApiError(409, { code: "event_quota_reached" }).message).toBe(quotaMessage("event_quota_reached"));
    expect(new StructuredApiError(400, { code: ["booking_quota_reached"] }).message).toBe(quotaMessage("booking_quota_reached"));
    expect(new StructuredApiError(403, { code: "event_quota_reached", detail: "Denied" }).message).toBe("Denied");
  });
  it("exposes the quota copy as the detail on 400 and 409, and the server's own detail otherwise", () => {
    expect(new StructuredApiError(409, { code: "payment_quota_reached", detail: "raw" }).detail).toBe(quotaMessage("payment_quota_reached"));
    expect(new StructuredApiError(500, { detail: "raw" }).detail).toBe("raw");
    expect(new StructuredApiError(500, {}).detail).toBeUndefined();
  });
  it("names the plan limit, with or without the resource", () => {
    expect(new StructuredApiError(409, { code: "plan_limit_reached", limit: " Members " }).message).toBe(`Members ${PLAN_LIMIT_MESSAGE}`);
    expect(new StructuredApiError(409, { code: "plan_limit_reached", limit: ["Staff"] }).message).toBe(`Staff ${PLAN_LIMIT_MESSAGE}`);
    expect(new StructuredApiError(409, { code: "plan_limit_reached", limit: "  " }).message).toBe(PLAN_LIMIT_MESSAGE);
    expect(new StructuredApiError(409, { code: "plan_limit_reached" }).message).toBe(PLAN_LIMIT_MESSAGE);
    expect(new StructuredApiError(409, { code: ["plan_limit_reached"] }).message).toBe(PLAN_LIMIT_MESSAGE);
  });
  it("falls back to the trimmed detail, then flattened body messages, then the status line", () => {
    expect(new StructuredApiError(400, { detail: "  Bad thing  " }).message).toBe("Bad thing");
    expect(new StructuredApiError(400, { name: ["Required.", " "], nested: { a: "Deep", b: ["List"] }, n: 5, empty: "" }).message).toBe("Required. Deep List");
    expect(new StructuredApiError(500, {}).message).toBe("Request failed (500)");
    expect(new StructuredApiError(502, { detail: 7 }).message).toBe("Request failed (502)");
  });
  it("keeps status, code and body, and reads Retry-After only when positive and numeric", () => {
    const error = new StructuredApiError(429, { code: "ip_blocked", detail: "d" }, new Headers({ "Retry-After": "30" }));
    expect(error).toMatchObject({ name: "StructuredApiError", status: 429, code: "ip_blocked", body: { code: "ip_blocked", detail: "d" }, retryAfterSeconds: 30 });
    expect(new StructuredApiError(429, {}, new Headers({ "Retry-After": "0" })).retryAfterSeconds).toBeUndefined();
    expect(new StructuredApiError(429, {}, new Headers({ "Retry-After": "soon" })).retryAfterSeconds).toBeUndefined();
    expect(new StructuredApiError(429, {}).retryAfterSeconds).toBeUndefined();
    expect(new StructuredApiError(429, { code: 5 }).code).toBeUndefined();
  });
});

describe("apiError", () => {
  it("builds a structured error from an object body", () => expect(apiError(400, { detail: "x" })).toMatchObject({ status: 400, message: "x" }));
  it.each([[null], [undefined], ["text"], [["a"]], [5]])("treats the non-object body %j as an empty body", (value) => {
    const error = apiError(500, value);
    expect(error.body).toEqual({});
    expect(error.message).toBe("Request failed (500)");
  });
  it("passes headers through for Retry-After", () => expect(apiError(429, {}, new Headers({ "Retry-After": "9" })).retryAfterSeconds).toBe(9));
});

describe("isSurfaceOff", () => {
  it.each(["module_disabled", "feature_disabled", "capability_disabled"])("is true for the typed %s refusal", (code) => expect(isSurfaceOff(new StructuredApiError(404, { code }))).toBe(true));
  it("is false for a plain 404, another code, a non-API error and non-errors", () => {
    expect(isSurfaceOff(new StructuredApiError(404, { detail: "nope" }))).toBe(false);
    expect(isSurfaceOff(new StructuredApiError(404, { code: "other" }))).toBe(false);
    expect(isSurfaceOff(new Error("x"))).toBe(false);
    expect(isSurfaceOff(null)).toBe(false);
  });
});

describe("status wording", () => {
  it.each([[401, "Inventory client is not authorized"], [404, "Makerspace not found"], [500, "Inventory service is unavailable"], [503, "Inventory service is unavailable"],
    [400, "Unable to load inventory"], [403, "Unable to load inventory"]])("status %i reads %s", (status, text) => expect(messageForStatus(status)).toBe(text));
  it("builds the generic failure line", () => expect(requestFailedMessage(418)).toBe("Request failed (418)"));
});
