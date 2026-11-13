import { describe, expect, it } from "vitest";

import { MEMBER_TABS, memberTabLabel, memberTabs } from "../MemberPortalTabs";

// Decision 246 / role-screen audit 0.12.0: the member area's sections per module and capability.
// Rows: [modules on, features on, tabs the member sees].
const ALL = ["membership", "request_workflow", "bookings", "events", "notifications"];
const CASES: [string, string[], string[] | undefined, string[]][] = [
  ["everything on", ALL, ["loans.enabled"], ["overview", "loans", "bookings", "events", "payments", "inbox", "account"]],
  ["no capability list (module-only rule)", ALL, undefined, ["overview", "loans", "bookings", "events", "payments", "inbox", "account"]],
  ["membership off (account-only borrower)", ALL.filter(m => m !== "membership"), ["loans.enabled"], ["overview", "bookings", "payments", "account"]],
  ["lending off", ALL, [], ["overview", "bookings", "events", "payments", "inbox", "account"]],
  ["request_workflow off", ALL.filter(m => m !== "request_workflow"), ["loans.enabled"], ["overview", "bookings", "events", "payments", "inbox", "account"]],
  ["bookings off", ALL.filter(m => m !== "bookings"), ["loans.enabled"], ["overview", "loans", "events", "payments", "inbox", "account"]],
  ["events off", ALL.filter(m => m !== "events"), ["loans.enabled"], ["overview", "loans", "bookings", "payments", "inbox", "account"]],
  ["notifications off", ALL.filter(m => m !== "notifications"), ["loans.enabled"], ["overview", "loans", "bookings", "events", "payments", "account"]],
  ["bookings-only space", ["bookings"], [], ["overview", "bookings", "payments", "account"]],
  ["nothing on", [], [], ["overview", "payments", "account"]],
];

describe("member area sections", () => {
  it.each(CASES)("%s", (_name, modules, features, expected) => {
    expect(memberTabs(modules, features)).toEqual(expected);
  });

  it("always keeps Home, Payments and Account (own debt stays readable, decision 213)", () => {
    for (const [, modules, features] of CASES) expect(memberTabs(modules, features)).toEqual(expect.arrayContaining(["overview", "payments", "account"]));
  });

  it("every section has a translated label that is not the raw key", () => {
    for (const tab of MEMBER_TABS) expect(memberTabLabel(tab)).toMatch(/^[A-Z][a-z]+$/);
  });
});
