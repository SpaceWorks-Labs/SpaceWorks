import { describe, expect, it } from "vitest";

import { DATA_FIELDS, SAMPLE_LONG, SAMPLE_SHORT, fieldsFor } from "./dataFields";

// Hard-coded mirror of TAGS + SENSITIVE_TAGS in backend/apps/card_designs/data_fields.py. Update both together.
const BACKEND_TAGS = ["name", "number", "plan", "valid_until", "member_since", "role", "title", "team", "track", "event",
  "space", "organisation", "programme", "issued_on", "verify_url", "certifications", "email", "crew_kind",
  "date", "time", "venue", "price", "order", "unit", "unit_code", "units", "level1", "level2", "level3", "level4",
  "roles", "machine_scope", "first_name", "last_name", "blood_group", "emergency_contact"];

describe("card data fields", () => {
  it("cover every backend tag, each with a sample value", () => {
    const keys = DATA_FIELDS.map((field) => field.key);
    expect(BACKEND_TAGS.filter((tag) => !keys.includes(tag))).toEqual([]);
    expect(keys.filter((key) => !BACKEND_TAGS.includes(key))).toEqual([]);
    expect(BACKEND_TAGS.filter((tag) => !(tag in SAMPLE_SHORT) || !(tag in SAMPLE_LONG))).toEqual([]);
  });

  it("offers ticket tags only on tickets and unit and staff tags only where they apply", () => {
    const on = (domain: string) => fieldsFor([], domain).map((field) => field.key);
    expect(on("event_ticket")).toContain("venue");
    expect(on("member_cards")).not.toContain("venue");
    expect(on("member_cards")).toContain("level2");
    expect(on("member_cards")).not.toContain("roles");
    expect(on("staff_cards")).toEqual(expect.arrayContaining(["roles", "machine_scope", "unit"]));
    expect(on("event_card")).not.toContain("unit");
    expect(fieldsFor([]).length).toBe(DATA_FIELDS.length);
  });
});
