// @vitest-environment node
import { readFileSync, writeFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import { AUDIT_AREA_ACTIONS, AUDIT_REPAIR_ACTIONS } from "./panels/auditAreas";
import { AREA_CHARGE_ACTIONS, SUBJECT_ACTION } from "./paymentAccess";
import { REFUND_SUBJECT_ACTIONS, STAFF_TAB_KEYS, getStaffAccess, staffLandingTab } from "./staffAccess";

/**
 * Mutation-testing pins (decision 457). `getStaffAccess` is a large pure function over (actions, flags): the fixture
 * `staffAccess.mutation.fixture.json` holds a hash of its COMPLETE result for every single action, every action beside a
 * handful of pivot actions, and every flag combination. Any change to who sees which tab changes a hash.
 * A deliberate permission change regenerates it:  UPDATE_STAFF_ACCESS_FIXTURE=1 npx vitest run src/features/staff/staffAccess.mutation.test.ts
 */
const FIXTURE = new URL("./staffAccess.mutation.fixture.json", import.meta.url);
const SOURCE = readFileSync(new URL("./staffAccess.ts", import.meta.url), "utf8");

function hash(text: string) {
  let a = 0x811c9dc5, b = 0x01000193;
  for (let i = 0; i < text.length; i++) {
    a = Math.imul(a ^ text.charCodeAt(i), 0x01000193) >>> 0;
    b = Math.imul(b + text.charCodeAt(i), 0x85ebca6b) >>> 0;
  }
  return a.toString(16).padStart(8, "0") + b.toString(16).padStart(8, "0");
}

const universe = [...new Set([
  ...(SOURCE.match(/"[a-z]+_[a-z_]+"/g) ?? []).map(token => token.slice(1, -1)),
  ...Object.values(AUDIT_AREA_ACTIONS).flat(), ...AUDIT_REPAIR_ACTIONS, ...AREA_CHARGE_ACTIONS, ...Object.values(SUBJECT_ACTION),
  ...REFUND_SUBJECT_ACTIONS, "view_analytics", "view_shop", "sell_shop", "manage_devices", "manage_member_cards", "scan_member_cards",
  "manage_member_units", "view_member_units", "some_unknown_action",
])].sort();
const PIVOTS = ["view_inventory", "issue_request", "manage_makerspace", "view_finance", "record_payment"];

function cells() {
  const out: Record<string, string> = {};
  const record = (actions: string[], sa: boolean, locked: boolean, ev: boolean, bk: boolean, orgs: boolean) => {
    const key = `${actions.join("+") || "-"}|${+sa}${+locked}${+ev}${+bk}${+orgs}`;
    out[key] = hash(JSON.stringify(getStaffAccess(actions, sa, locked, false, ev, bk, orgs)));
  };
  const flags = (fn: (sa: boolean, locked: boolean, ev: boolean, bk: boolean, orgs: boolean) => void) => {
    for (const sa of [false, true]) for (const locked of [false, true]) for (const ev of [false, true]) for (const bk of [false, true]) for (const orgs of [false, true]) fn(sa, locked, ev, bk, orgs);
  };
  flags((...f) => record([], ...f));
  flags((...f) => record(universe, ...f));
  for (const action of universe) flags((...f) => record([action], ...f));
  for (const pivot of PIVOTS) for (const action of universe) {
    if (action === pivot) continue;
    for (const sa of [false, true]) for (const locked of [false, true]) for (const grants of [false, true]) record([pivot, action].sort(), sa, locked, grants, false, true);
  }
  return out;
}

describe("getStaffAccess characterization (every action x flag cell)", () => {
  it("matches the committed permission matrix exactly", () => {
    const now = cells();
    if (process.env.UPDATE_STAFF_ACCESS_FIXTURE) writeFileSync(FIXTURE, JSON.stringify(now, null, 0));
    const expected = JSON.parse(readFileSync(FIXTURE, "utf8")) as Record<string, string>;
    expect(Object.keys(now).length).toBe(Object.keys(expected).length);
    const wrong = Object.keys(now).filter(key => expected[key] !== now[key]);
    expect(wrong.slice(0, 20)).toEqual([]);
  });
});

describe("staffLandingTab and the tab/action tables", () => {
  it("lands on dashboard, then shop, repairs, donations, else the first tab, else nothing", () => {
    expect(staffLandingTab(["requests", "donations", "repairs", "shop", "dashboard"])).toBe("dashboard");
    expect(staffLandingTab(["requests", "donations", "repairs", "shop"])).toBe("shop");
    expect(staffLandingTab(["requests", "donations", "repairs"])).toBe("repairs");
    expect(staffLandingTab(["requests", "donations"])).toBe("donations");
    expect(staffLandingTab(["requests", "ledger"])).toBe("requests");
    expect(staffLandingTab([])).toBeUndefined();
  });
  it("pins the tab key list and the refund subject authorities", () => {
    expect(hash(STAFF_TAB_KEYS.join(","))).toBe(hash("platform-dashboard,platform-spaces,platform-inbox,platform-access,platform-security,platform-data,platform-limits,usage,dashboard,notifications,channels,requests,direct,handover,inventory,needsfix,categories,machines,events,organized,granted,bookings,members,cards,tobuy,transfers,stocktake,containers,ledger,reports,accountability,warranty,bulk,qr,scanner,api,settings,security,emailtemplates,users,platform,audit,devices,email-logs,payments,refunds,finance,organizations,organization-analytics,modules,exports,backups,migration,consumables,repairs,incidents,schedule,shop,donations,analytics,platform-analytics"));
    expect([...REFUND_SUBJECT_ACTIONS]).toEqual(["issue_request", "return_request", "manage_shop", "manage_donations"]);
  });
  it("defaults: no event or booking grants, an organization member, and the machine-only flag is ignored", () => {
    for (const actions of [[], ["manage_events"], ["view_inventory", "issue_request"]]) {
      for (const [sa, locked] of [[false, false], [false, true], [true, false], [true, true]]) {
        const explicit = getStaffAccess(actions, sa, locked, false, false, false, true);
        expect(getStaffAccess(actions, sa, locked)).toEqual(explicit);
        expect(getStaffAccess(actions, sa, locked, true)).toEqual(explicit);
      }
    }
    expect(getStaffAccess([], false, false).allowedTabs).toEqual(["organizations", "organized", "organization-analytics"]);
    expect(getStaffAccess([], false, false, false, true).allowedTabs).toEqual(["granted", "organizations", "organized", "organization-analytics"]);
    expect(getStaffAccess([], false, false, false, false, true).allowedTabs).toEqual(["granted", "organizations", "organized", "organization-analytics"]);
    expect(getStaffAccess([], false, false, false, false, false, false).allowedTabs).toEqual(["organizations"]);
  });
});
