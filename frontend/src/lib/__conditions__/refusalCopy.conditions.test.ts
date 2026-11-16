import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { apiError, isSurfaceOff, requestFailedMessage, StructuredApiError, SPACE_READ_ONLY_MESSAGE, SPACE_SUSPENDED_MESSAGE, PLAN_LIMIT_MESSAGE } from "../api/errors";
import { eligibilityMessage, refusalCode } from "../eligibilityCopy";

// Decision 246: refusal-code copy. The codes are read from the copy modules themselves, so a code added
// later is covered automatically and a code that loses its copy fails here.
const source = (file: string) => readFileSync(join(process.cwd(), "src", "lib", file), "utf8");
const codesIn = (file: string) => [...source(file).matchAll(/case "([a-z_]+)"/g)].map(match => match[1]);
const CODES = [...new Set([...codesIn("eligibilityCopy.ts"), ...codesIn("guestRefusalCopy.ts")])];
// Decision 235: no internal jargon in user-facing text.
const JARGON = /\b(module key|capability|tenant|managed|traceback|exception|null|undefined|\bAPI\b)\b/i;

describe("refusal copy", () => {
  it("covers a meaningful number of codes", () => expect(CODES.length).toBeGreaterThan(40));

  it.each(CODES)("%s: plain sentence that says what to do, with no jargon", code => {
    const message = eligibilityMessage(new StructuredApiError(403, { code }));
    expect(message, code).toBeTruthy();
    expect(message).toMatch(/[.!]$/);
    expect(message).not.toMatch(JARGON);
    expect(message).not.toContain(code);
  });

  it.each(CODES)("%s: also resolved from DRF's list-shaped code", code => {
    expect(eligibilityMessage(new StructuredApiError(400, { code: [code] }))).toBe(eligibilityMessage(new StructuredApiError(403, { code })));
  });

  it.each([[undefined], ["unknown_code"], [""]])("code %j falls through to the surface's own fallback", code => {
    expect(eligibilityMessage(new StructuredApiError(403, code === undefined ? {} : { code }))).toBeNull();
  });

  it("ignores errors that are not structured API errors", () => {
    expect(eligibilityMessage(new Error("boom"))).toBeNull();
    expect(refusalCode("membership_required")).toBeUndefined();
  });
});

describe("space-level refusals (423 and plan limits)", () => {
  it.each([
    [423, "space_read_only", SPACE_READ_ONLY_MESSAGE],
    [423, "space_suspended", SPACE_SUSPENDED_MESSAGE],
  ])("%i %s explains itself instead of the raw server text", (status, code, message) => {
    expect(apiError(status, { code, detail: "raw server text" }).message).toBe(message);
  });

  it("keeps the named limit and adds what to do; falls back to the generic sentence", () => {
    expect(apiError(400, { code: "plan_limit_reached", limit: "Members" }).message).toBe(`Members ${PLAN_LIMIT_MESSAGE}`);
    expect(apiError(400, { code: ["plan_limit_reached"] }).message).toBe(PLAN_LIMIT_MESSAGE);
  });

  it.each([
    [{ detail: "  Nope  " }, "Nope"],
    [{ field: ["bad value"] }, "bad value"],
    [{}, requestFailedMessage(500)],
  ])("falls back to detail, field messages, then a generic line: %j", (body, expected) => {
    expect(apiError(500, body).message).toBe(expected);
  });

  it.each([["module_disabled", true], ["feature_disabled", true], ["capability_disabled", true], ["not_found", false]])(
    "%s is a switched-off surface: %s", (code, off) => {
      expect(isSurfaceOff(apiError(404, { code }))).toBe(off);
    });

  it("reads Retry-After from a rate-limit refusal", () => {
    expect(apiError(429, { code: "ip_blocked" }, new Headers({ "Retry-After": "90" })).retryAfterSeconds).toBe(90);
    expect(apiError(429, {}, new Headers({ "Retry-After": "soon" })).retryAfterSeconds).toBeUndefined();
  });
});
