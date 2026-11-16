import { describe, expect, it } from "vitest";

import type { StaffAuthUser } from "../../lib/api";
import { consoleSpaceIds, hasConsoleAccess, isSuperadminUser, mfaGate } from "./consoleAccess";

const user = (over: Record<string, unknown> = {}) => ({ is_superuser: false, role: "member", makerspaces: [], ...over }) as unknown as StaffAuthUser;
const NOW = Date.parse("2026-11-13T10:00:00Z");

describe("isSuperadminUser", () => {
  it("is the superuser flag or the superadmin role, nothing else", () => {
    expect(isSuperadminUser(user({ is_superuser: true }))).toBe(true);
    expect(isSuperadminUser(user({ role: "superadmin" }))).toBe(true);
    expect(isSuperadminUser(user({ role: "space_manager" }))).toBe(false);
    expect(isSuperadminUser(user())).toBe(false);
  });
});

describe("consoleSpaceIds", () => {
  it("collects staff-role spaces, organization-authority spaces with actions, and event and booking grants", () => {
    const ids = consoleSpaceIds(user({
      staff_roles: [{ makerspace: { id: 1 } }],
      makerspaces: [{ id: 2, source: "organization", actions: ["manage_events"] }],
      event_grants: [{ makerspace_id: 3 }],
      booking_grants: [{ makerspace_id: 4 }],
    }));
    expect([...ids].sort()).toEqual([1, 2, 3, 4]);
  });
  it("ignores a community membership, an organization space with no actions and any other source", () => {
    const ids = consoleSpaceIds(user({ makerspaces: [
      { id: 5, source: "membership", actions: ["manage_events"] },
      { id: 6, source: "organization", actions: [] },
      { id: 7, source: "staff", actions: ["manage_events"] },
    ] }));
    expect(ids.size).toBe(0);
  });
  it("copes with missing role and grant lists and de-duplicates a space reached twice", () => {
    expect(consoleSpaceIds(user()).size).toBe(0);
    const ids = consoleSpaceIds(user({ staff_roles: [{ makerspace: { id: 1 } }], event_grants: [{ makerspace_id: 1 }], booking_grants: [{ makerspace_id: 1 }] }));
    expect([...ids]).toEqual([1]);
  });
});

describe("hasConsoleAccess", () => {
  it("opens for the superadmin, elevated authority, or any reachable space", () => {
    expect(hasConsoleAccess(user({ is_superuser: true }))).toBe(true);
    expect(hasConsoleAccess(user({ role: "superadmin" }))).toBe(true);
    expect(hasConsoleAccess(user({ has_elevated_authority: true }))).toBe(true);
    expect(hasConsoleAccess(user({ booking_grants: [{ makerspace_id: 9 }] }))).toBe(true);
  });
  it("stays closed for a plain member", () => {
    expect(hasConsoleAccess(user())).toBe(false);
    expect(hasConsoleAccess(user({ has_elevated_authority: false, makerspaces: [{ id: 1, source: "membership", actions: ["x"] }] }))).toBe(false);
  });
});

describe("mfaGate", () => {
  const due = (ends?: string | null) => user({ mfa_enrolment_due: true, mfa_grace_ends_at: ends });
  it("needs nothing from the superadmin or from someone not due", () => {
    expect(mfaGate(user({ is_superuser: true, mfa_enrolment_due: true }), NOW)).toBe("none");
    expect(mfaGate(user({ role: "superadmin", mfa_enrolment_due: true }), NOW)).toBe("none");
    expect(mfaGate(user({ mfa_enrolment_due: false }), NOW)).toBe("none");
    expect(mfaGate(user(), NOW)).toBe("none");
  });
  it("is grace while the end is in the future, required at or after it, and required with no end or a bad one", () => {
    expect(mfaGate(due("2026-11-13T10:00:01Z"), NOW)).toBe("grace");
    expect(mfaGate(due("2026-11-13T10:00:00Z"), NOW)).toBe("required");
    expect(mfaGate(due("2026-11-13T09:59:59Z"), NOW)).toBe("required");
    expect(mfaGate(due(null), NOW)).toBe("required");
    expect(mfaGate(due(undefined), NOW)).toBe("required");
    expect(mfaGate(due(""), NOW)).toBe("required");
    expect(mfaGate(due("not a date"), NOW)).toBe("required");
  });
  it("defaults now to the clock", () => {
    expect(mfaGate(due(new Date(Date.now() + 3_600_000).toISOString()))).toBe("grace");
    expect(mfaGate(due(new Date(Date.now() - 3_600_000).toISOString()))).toBe("required");
  });
});
