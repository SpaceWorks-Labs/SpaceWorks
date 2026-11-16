import { describe, expect, it } from "vitest";
import { parseDetail, parseExport, parseFormSaveIntents, parseIntent, parsePrefill, parseResume, parseSavedDetails } from "./parsers";

const UNREADABLE = "Saved details could not be read. Try again.";
const UUID = "123e4567-e89b-12d3-a456-426614174000";
const UUID2 = "223e4567-e89b-12d3-a456-426614174000";
const SHA = "a".repeat(64);
const field = (over: Record<string, unknown> = {}) => ({ field_key: "name", value: "Ann", version: 1, sensitive: false, default_save: true, ...over });
const saved = (fields: unknown[], over: Record<string, unknown> = {}) => ({ version: 1, readiness: "ready", fields, ...over });

describe("parseSavedDetails", () => {
  it("accepts every value shape", () => {
    const data = saved([field(), field({ field_key: "skills", value: ["a", "b"] }), field({ field_key: "resume", value: { asset_id: 4, sha256: SHA } }),
      field({ field_key: "emergency_contact", value: { name: "n", relationship: "r", phone: "p" } }), field({ field_key: "phone", value: null })]);
    expect(parseSavedDetails(data)).toBe(data);
  });
  it.each([["null", null], ["array", []], ["string", "x"]])("refuses a %s payload with the readable message", (_n, value) => expect(() => parseSavedDetails(value)).toThrow(UNREADABLE));
  it.each([
    ["a non-integer version", saved([], { version: 1.5 })], ["a negative version", saved([], { version: -1 })], ["fields that are not a list", saved("x" as never)],
    ["an unknown readiness", saved([], { readiness: "maybe" })],
    ["an unknown field key", saved([field({ field_key: "age_at_event" })])],
    ["a duplicated field", saved([field(), field()])],
    ["a zero field version", saved([field({ version: 0 })])],
    ["a non-boolean sensitive flag", saved([field({ sensitive: "yes" })])],
    ["a non-boolean default_save", saved([field({ default_save: 1 })])],
    ["a non-string plain value", saved([field({ value: 5 })])],
    ["a skills value that is not strings", saved([field({ field_key: "skills", value: ["a", 2] })])],
    ["a skills value that is not a list", saved([field({ field_key: "skills", value: "a" })])],
    ["an emergency contact missing a part", saved([field({ field_key: "emergency_contact", value: { name: "n", relationship: "r" } })])],
    ["a resume without a valid hash", saved([field({ field_key: "resume", value: { asset_id: 4, sha256: "short" } })])],
    ["a resume with a zero asset id", saved([field({ field_key: "resume", value: { asset_id: 0, sha256: SHA } })])],
  ])("refuses %s", (_n, value) => expect(() => parseSavedDetails(value)).toThrow(UNREADABLE));
  it("accepts the unavailable readiness", () => expect(parseSavedDetails(saved([], { readiness: "unavailable" })).readiness).toBe("unavailable"));
});

describe("parsePrefill", () => {
  const prefill = (over: Record<string, unknown> = {}) => ({ form_revision: 2, event_date_revision: 3, values: { name: "Ann" }, saved_detail_versions: { name: 1 },
    save_defaults: { name: true }, derivation_inputs: {}, ...over });
  it("accepts a well-formed prefill", () => expect(parsePrefill(prefill())).toEqual(prefill()));
  it.each([
    ["a zero form revision", prefill({ form_revision: 0 })], ["a missing event date revision", prefill({ event_date_revision: undefined })],
    ["an unknown value key", prefill({ values: { nope: 1 } })], ["an unknown version key", prefill({ saved_detail_versions: { nope: 1 } })],
    ["a negative saved version", prefill({ saved_detail_versions: { name: -1 } })], ["a non-boolean save default", prefill({ save_defaults: { name: "yes" } })],
    ["a missing values object", prefill({ values: undefined })],
  ])("refuses %s", (_n, value) => expect(() => parsePrefill(value)).toThrow(UNREADABLE));
  const derivation = (over: Record<string, unknown> = {}) => ({ source: { kind: "saved_detail", field_key: "date_of_birth", version: 2, ...((over.source as object) ?? {}) },
    value: 22, as_of_date: "2026-05-01", ...over });
  it("accepts a saved date-of-birth derivation", () => expect(parsePrefill(prefill({ derivation_inputs: { age: derivation() } })).derivation_inputs).toBeDefined());
  it.each([
    ["another source kind", derivation({ source: { kind: "inline_dob" } })], ["another source field", derivation({ source: { field_key: "name" } })],
    ["a zero source version", derivation({ source: { version: 0 } })], ["a negative derived value", derivation({ value: -1 })],
    ["a malformed as-of date", derivation({ as_of_date: "May 1" })],
  ])("refuses a derivation with %s", (_n, d) => expect(() => parsePrefill(prefill({ derivation_inputs: { age: d } }))).toThrow(UNREADABLE));
  describe("staged (anonymous) prefill", () => {
    it("accepts a staged prefill with no date of birth", () => expect(parsePrefill(prefill(), true)).toEqual(prefill()));
    it.each(["values", "saved_detail_versions", "save_defaults"])("refuses date_of_birth inside %s", (name) =>
      expect(() => parsePrefill(prefill({ [name]: { date_of_birth: name === "values" ? "2000-01-01" : name === "save_defaults" ? true : 1 } }), true)).toThrow(UNREADABLE));
    it("refuses age_at_event inside values", () => expect(() => parsePrefill(prefill({ values: { age_at_event: 5 } }), true)).toThrow(UNREADABLE));
    it("refuses any derivation input", () => expect(() => parsePrefill(prefill({ derivation_inputs: { age: derivation() } }), true)).toThrow(UNREADABLE));
    it("allows a date of birth when not staged", () => expect(parsePrefill(prefill({ values: { date_of_birth: "2000-01-01" } })).values).toEqual({ date_of_birth: "2000-01-01" }));
  });
});

describe("parseResume", () => {
  const resume = (over: Record<string, unknown> = {}) => ({ asset_id: 4, state: "ready", sha256: SHA, version: 1, bytes: 10, ...over });
  it("accepts a ready resume", () => expect(parseResume(resume())).toEqual(resume()));
  it("accepts a non-ready state without a hash", () => expect(parseResume({ asset_id: 4, state: "failed" }).state).toBe("failed"));
  it.each([
    ["a zero asset id", resume({ asset_id: 0 })], ["an unknown state", resume({ state: "weird" })], ["a ready resume without a hash", resume({ sha256: undefined })],
    ["a ready resume with zero bytes", resume({ bytes: 0 })], ["a ready resume with a zero version", resume({ version: 0 })],
  ])("refuses %s", (_n, value) => expect(() => parseResume(value)).toThrow(UNREADABLE));
  const upload = (over: Record<string, unknown> = {}) => resume({ state: "uploading", upload: { method: "POST", url: "https://s3/x", expires_at: "2026-05-01T00:00:00Z",
    fields: { key: "staging/account/1/file", policy: "p" }, ...over } });
  it("accepts a staged upload form", () => expect(parseResume(upload()).state).toBe("uploading"));
  it.each([
    ["a PUT upload", { method: "PUT" }], ["no url", { url: undefined }], ["no expiry", { expires_at: undefined }],
    ["a non-string form field", { fields: { key: "staging/account/1/f", n: 1 } }], ["a key outside the staging prefix", { fields: { key: "final/x" } }],
    ["no key", { fields: { policy: "p" } }],
  ])("refuses %s", (_n, over) => expect(() => parseResume(upload(over))).toThrow(UNREADABLE));
});

describe("parseExport", () => {
  it.each(["queued", "building", "ready", "failed", "expired"])("accepts state %s", (state) => expect(parseExport({ job_id: UUID, state }).state).toBe(state));
  it.each([["a bad job id", { job_id: "abc", state: "ready" }], ["an unknown state", { job_id: UUID, state: "done" }]])("refuses %s", (_n, value) => expect(() => parseExport(value)).toThrow(UNREADABLE));
});

describe("parseIntent", () => {
  const intent = (over: Record<string, unknown> = {}) => ({ operation_id: UUID, state: "applied", retryable: false, fields: { name: { state: "applied", version: 2 } }, ...over });
  it("accepts a well-formed intent", () => expect(parseIntent(intent())).toEqual(intent()));
  it.each([
    ["a bad operation id", intent({ operation_id: "x" })], ["an unknown state", intent({ state: "queued" })], ["a non-boolean retryable", intent({ retryable: "no" })],
    ["an unknown field key", intent({ fields: { nope: { state: "applied" } } })], ["an unknown field state", intent({ fields: { name: { state: "weird" } } })],
    ["a zero field version", intent({ fields: { name: { state: "applied", version: 0 } } })], ["a negative current version", intent({ fields: { name: { state: "conflict", current_version: -1 } } })],
  ])("refuses %s", (_n, value) => expect(() => parseIntent(value)).toThrow(UNREADABLE));
  it("accepts a conflict that reports the current version", () => expect(parseIntent(intent({ state: "conflict", fields: { name: { state: "conflict", current_version: 0 } } })).state).toBe("conflict"));
});

describe("parseFormSaveIntents", () => {
  const item = (over: Record<string, unknown> = {}) => ({ slot: "base", operation_id: UUID, intent_id: UUID2, state: "applied", fields: { name: { state: "applied" } },
    status_url: `/api/v1/member/saved-details/save-intents/${UUID}/`, ...over });
  it("accepts base and numbered stage slots", () => {
    const list = [item(), item({ slot: "stage:2", operation_id: UUID2, status_url: `/api/v1/member/saved-details/save-intents/${UUID2}/` })];
    expect(parseFormSaveIntents(list)).toBe(list);
  });
  it("accepts a not-requested slot that has no intent, status url or fields", () => expect(parseFormSaveIntents([item({ state: "not_requested", intent_id: null, status_url: null, fields: {} })])).toHaveLength(1));
  it("refuses a value that is not a list", () => expect(() => parseFormSaveIntents({})).toThrow(UNREADABLE));
  it.each([
    ["an unknown slot", item({ slot: "stage:0" })], ["a malformed slot", item({ slot: "other" })], ["a bad operation id", item({ operation_id: "x" })],
    ["an intent id that is not a uuid", item({ intent_id: "x" })], ["an unknown state", item({ state: "weird" })],
    ["a status url for another operation", item({ status_url: "/api/v1/member/saved-details/save-intents/other/" })],
    ["a not-requested slot that carries fields", item({ state: "not_requested", intent_id: null, status_url: null })],
    ["a not-requested slot with an intent id", item({ state: "not_requested", intent_id: UUID2, status_url: null, fields: {} })],
  ])("refuses %s", (_n, value) => expect(() => parseFormSaveIntents([value])).toThrow(UNREADABLE));
  it("refuses a repeated slot and a repeated operation, comparing operation ids case-insensitively", () => {
    expect(() => parseFormSaveIntents([item(), item({ operation_id: UUID2 })])).toThrow(UNREADABLE);
    expect(() => parseFormSaveIntents([item(), item({ slot: "stage:1", operation_id: UUID.toUpperCase() })])).toThrow(UNREADABLE);
  });
});

describe("parseDetail", () => {
  it("accepts a known key with a positive version", () => expect(parseDetail({ field_key: "name", version: 3, value: "A" })).toEqual({ field_key: "name", version: 3, value: "A" }));
  it.each([["an unknown key", { field_key: "x", version: 1 }], ["a zero version", { field_key: "name", version: 0 }]])("refuses %s", (_n, value) => expect(() => parseDetail(value)).toThrow(UNREADABLE));
});
