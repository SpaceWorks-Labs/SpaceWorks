import { expect, it } from "vitest";
import { sanitizeSentryEvent } from "./sentry";
it("retains bounded same-origin code frames while removing secret event fields", () => {
  const result = sanitizeSentryEvent({ type: undefined, event_id: "abc", message: "secret-message", user: { email: "secret@example.test" }, request: { url: "https://example.test/?token=secret" }, extra: { private: "secret-extra" }, breadcrumbs: [{ message: "secret-crumb" }], exception: { values: [{ type: "TypeError", value: "secret-message", stacktrace: { frames: [
    { filename: `${location.origin}/assets/app.js?token=secret#private`, lineno: 12, colno: 3, function: "safeFunction", vars: { secret: "secret-vars" } },
    { filename: "https://foreign.test/assets/external.js?secret=1", lineno: 1 }, { filename: `${location.origin}/private?secret=1`, lineno: 4 },
  ] } }] } });
  expect(result.exception?.values?.[0]?.type).toBe("TypeError"); expect(result.exception?.values?.[0]?.stacktrace?.frames).toEqual([{ filename: "/assets/app.js", lineno: 12, colno: 3, function: "safeFunction" }]);
  expect(JSON.stringify(result)).not.toMatch(/secret|foreign|private|example/);
});
it("normalizes unknown exception names and drops unsafe function and frame values", () => {
  const result = sanitizeSentryEvent({ type: undefined, exception: { values: [{ type: "secret-name", stacktrace: { frames: [{ filename: `${location.origin}/src/main.ts`, lineno: -1, function: "secret()" }] } }] } });
  expect(result.exception?.values?.[0]?.type).toBe("Error"); expect(JSON.stringify(result)).not.toContain("secret");
});
