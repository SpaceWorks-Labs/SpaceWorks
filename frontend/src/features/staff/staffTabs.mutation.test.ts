import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { beforeEach, describe, expect, it } from "vitest";

import { STAFF_TAB_KEYS } from "./staffAccess";
import {
  STAFF_ACTIVE_TAB_KEY, STAFF_SELECTED_MAKERSPACE_KEY, SUPERADMIN_GLOBAL_TABS, TAB_FEATURES, TAB_MODULES, filterTabsByEnabledModules,
  keptStaffSubPath, persistSelectedMakerspace, persistStaffTab, readStoredMakerspace, readStoredStaffTab, staffBasePath,
  staffMakerspaceSlugFromPath, staffPathState, staffSubPathFromPath, staffTabPath, tabFromStaffPath, tabToPath,
} from "./staffTabs";

/**
 * Mutation-testing pins (decision 457) for the nav module gate and routing helpers. The fixtures hold a hash of the
 * complete output for every tab under many module/feature/app/action configurations and every path shape; any change
 * to which tab a switch hides, or how a tab maps to a URL, changes a hash.
 * A deliberate change regenerates them:  UPDATE_STAFF_TABS_FIXTURE=1 npx vitest run src/features/staff/staffTabs.mutation.test.ts
 */
function hash(text: string) {
  let a = 0x811c9dc5, b = 0x01000193;
  for (let i = 0; i < text.length; i++) {
    a = Math.imul(a ^ text.charCodeAt(i), 0x01000193) >>> 0;
    b = Math.imul(b + text.charCodeAt(i), 0x85ebca6b) >>> 0;
  }
  return a.toString(16).padStart(8, "0") + b.toString(16).padStart(8, "0");
}

const TABS = [...new Set([...STAFF_TAB_KEYS, "printing", "machine-service", "warranty", "unknown-tab"])];
const MODULES = [...new Set(Object.values(TAB_MODULES).flat()), "machines", "events", "bookings", "membership", "some_other_module"];
const FEATURES = [...new Set([...Object.values(TAB_FEATURES).flat(), "loans.enabled", "inventory.self_checkout", "machines.repairs",
  "inventory.repairs", "machines.tobuy", "inventory.tobuy", "machines.warranty", "inventory.warranty", "bookings.room_repairs", "inventory.issue_reporting"])];
const APPS = ["events", "bookings", "warranty", "tenant_migration", "other_app"];
const ACTIONS: (string[] | undefined)[] = [undefined, [], ["manage_makerspace"], ["manage_machines"], ["edit_inventory"], ["manage_bookings"],
  ["manage_printing"], ["manage_machines", "manage_bookings"], ["view_inventory"], ["manage_makerspace", "manage_machines"],
  ["manage_makerspace", "edit_inventory"]];

type Space = { enabled_modules?: string[]; enabled_features?: string[]; unavailable_apps?: string[] };

function filterCells() {
  const out: Record<string, string> = {};
  const put = (label: string, space: Space | undefined) => {
    ACTIONS.forEach((actions, i) => {
      out[`${label}|a${i}`] = hash(filterTabsByEnabledModules(TABS, space as never, actions).join(","));
    });
  };
  put("none", undefined);
  put("empty", {});
  put("modules-undefined", { enabled_features: FEATURES, unavailable_apps: [] });
  put("unavailable-only", { unavailable_apps: ["events"] });
  put("modules-none", { enabled_modules: [], enabled_features: FEATURES });
  put("modules-all", { enabled_modules: MODULES, enabled_features: FEATURES });
  put("features-undefined-all-modules", { enabled_modules: MODULES });
  put("features-undefined-no-modules", { enabled_modules: [] });
  put("features-none", { enabled_modules: MODULES, enabled_features: [] });
  for (const m of MODULES) {
    put(`only-module:${m}`, { enabled_modules: [m], enabled_features: FEATURES });
    put(`only-module-nofeat:${m}`, { enabled_modules: [m] });
    put(`all-but-module:${m}`, { enabled_modules: MODULES.filter(x => x !== m), enabled_features: FEATURES });
  }
  for (const f of FEATURES) {
    put(`only-feature:${f}`, { enabled_modules: MODULES, enabled_features: [f] });
    put(`only-feature+loans:${f}`, { enabled_modules: MODULES, enabled_features: [f, "loans.enabled"] });
    put(`all-but-feature:${f}`, { enabled_modules: MODULES, enabled_features: FEATURES.filter(x => x !== f) });
  }
  for (const app of APPS) put(`unavailable:${app}`, { enabled_modules: MODULES, enabled_features: FEATURES, unavailable_apps: [app] });
  put("unavailable:empty-string", { enabled_modules: MODULES, enabled_features: FEATURES, unavailable_apps: [""] });
  put("unavailable:events+bookings", { enabled_modules: MODULES, enabled_features: FEATURES, unavailable_apps: ["events", "bookings"] });
  put("unavailable:events+bookings,no-modules", { unavailable_apps: ["events", "bookings"] });
  put("machines-module-no-loans", { enabled_modules: ["machines"], enabled_features: ["inventory.warranty"] });
  return out;
}

const PATHS = (() => {
  const out: string[] = ["", "/", "/admin", "/admin/", "/guest-admin", "/guest-admin/", "/x", "/adminx", "/m/s/admin", "/m/s/admin/", "/m//admin", "/m/s/other",
    "/x/m/s/admin/inventory", "/m/s/admin/inventory\nz", "/m/s/admin/inventory/a\nb", "/admintab//x", "/adminx//y", "/admin\nx", "/guest-admintab//x"];
  const extra = ["to-be-fixed", "direct-handout", "member-cards", "assigned-events", "organized-events", "email-log", "email-templates", "api-access",
    "backup-restore", "data-export", "tenant-migration", "qr-tools", "bulk-import", "to-buy"];
  for (const tab of TABS.concat(extra)) {
    for (const base of ["/admin", "/guest-admin", "/m/space-1/admin", "/m/space-1/guest-admin"]) {
      out.push(`${base}/${tab}`, `${base}/${tab}/`, `${base}/${tab}/a/b`, `${base}/${tab}///a//b///`, `${base}//${tab}`);
    }
  }
  return out;
})();

function pathCells() {
  const out: Record<string, string> = {};
  for (const tab of TABS) {
    for (const guest of [false, true]) for (const slug of [undefined, null, "", "s-1"]) for (const locked of [false, true]) for (const sub of ["", "x", "x/y"]) {
      out[`path|${tab}|${+guest}|${slug}|${+locked}|${sub}`] = staffTabPath(tab, guest, slug, locked, sub);
    }
    out[`path-default|${tab}`] = staffTabPath(tab, false);
    out[`tabToPath|${tab}`] = tabToPath(tab);
  }
  for (const p of PATHS) for (const guest of [false, true]) {
    out[`state|${p}|${+guest}`] = JSON.stringify([staffPathState(p, guest), staffSubPathFromPath(p, guest), staffMakerspaceSlugFromPath(p, guest), tabFromStaffPath(p, guest)]);
  }
  return Object.fromEntries(Object.entries(out).map(([k, v]) => [k, hash(v)]));
}

function check(name: string, now: Record<string, string>) {
  const file = join(process.cwd(), "src/features/staff", `staffTabs.mutation.${name}.fixture.json`);
  if (process.env.UPDATE_STAFF_TABS_FIXTURE) writeFileSync(file, JSON.stringify(now));
  const expected = JSON.parse(readFileSync(file, "utf8")) as Record<string, string>;
  expect(Object.keys(now).length).toBe(Object.keys(expected).length);
  expect(Object.keys(now).filter(key => expected[key] !== now[key]).slice(0, 20)).toEqual([]);
}

describe("staff tab module gate and routing characterization", () => {
  it("filterTabsByEnabledModules matches the committed matrix", () => check("filter", filterCells()));
  it("path building and parsing match the committed matrix", () => check("paths", pathCells()));
});

describe("staff tab constants and small helpers", () => {
  beforeEach(() => window.localStorage.clear());

  it("pins the module and feature tables the nav is gated by", () => {
    expect(TAB_MODULES).toEqual({
      direct: ["public_inventory"], notifications: ["notifications"], machines: ["machines"], devices: ["devices"], handover: ["machine_service"],
      events: ["events"], bookings: ["bookings"], cards: ["membership"], transfers: ["stock_transfers"], stocktake: ["stocktake"],
      containers: ["containers"], bulk: ["bulk_import"], qr: ["qr_print_batches"], scanner: ["scanner"], reports: ["reports"], shop: ["shop"], analytics: ["analytics"],
    });
    expect(TAB_FEATURES).toEqual({
      tobuy: ["inventory.tobuy", "machines.tobuy"], warranty: ["inventory.warranty", "machines.warranty"],
      finance: ["finance.ledger", "billing.offline_claims", "billing.maker_checker", "billing.capture_flags", "billing.disputes", "billing.collection_sheet"],
      donations: ["finance.donations", "finance.sponsors"], consumables: ["inventory.consumables"],
      repairs: ["machines.repairs", "machines.issue_reporting", "inventory.repairs", "inventory.issue_reporting", "bookings.room_repairs", "bookings.issue_reporting", "inventory.maintenance", "bookings.room_maintenance"],
      incidents: ["safety.incidents"],
    });
    expect([...SUPERADMIN_GLOBAL_TABS]).toEqual(["platform-dashboard", "platform-spaces", "platform-inbox", "platform-access", "platform-security", "platform-data", "platform-limits", "platform", "platform-analytics"]);
    expect([STAFF_SELECTED_MAKERSPACE_KEY, STAFF_ACTIVE_TAB_KEY]).toEqual(["spaceworks.staff.selectedMakerspace", "spaceworks.staff.activeTab"]);
  });

  it("staffTabPath scopes to the makerspace by default when a slug is given", () => {
    expect(staffTabPath("inventory", false, "s-1")).toBe("/m/s-1/admin/inventory");
    expect(staffTabPath("inventory", true, "s-1")).toBe("/m/s-1/admin/inventory");
    expect(staffTabPath("inventory", true, "s-1", true)).toBe("/guest-admin/inventory");
    expect(staffTabPath("organizations", false, "s-1")).toBe("/admin/organizations");
  });

  it("base paths and the kept sub-path rule", () => {
    expect(staffBasePath(false)).toBe("/admin");
    expect(staffBasePath(true)).toBe("/guest-admin");
    expect(keptStaffSubPath("machines", "machines", "12-laser")).toBe("12-laser");
    expect(keptStaffSubPath("machines", "events", "12-laser")).toBe("");
    expect(keptStaffSubPath("", "", "12-laser")).toBe("");
  });

  it("stores the selected makerspace and tab per session context, and clears them", () => {
    expect(readStoredMakerspace("person")).toBeNull();
    persistSelectedMakerspace(7, "person");
    expect(window.localStorage.getItem("spaceworks.staff.selectedMakerspace:person")).toBe("7");
    expect(readStoredMakerspace("person")).toBe(7);
    expect(readStoredMakerspace("platform")).toBeNull();
    for (const bad of ["0", "-3", "abc"]) {
      window.localStorage.setItem("spaceworks.staff.selectedMakerspace:person", bad);
      expect(readStoredMakerspace("person")).toBeNull();
    }
    persistSelectedMakerspace(7, "person");
    persistSelectedMakerspace(null, "person");
    expect(window.localStorage.getItem("spaceworks.staff.selectedMakerspace:person")).toBeNull();

    persistStaffTab("inventory", "person");
    expect(window.localStorage.getItem("spaceworks.staff.activeTab:person")).toBe("inventory");
    persistStaffTab("", "person");
    expect(window.localStorage.getItem("spaceworks.staff.activeTab:person")).toBeNull();
  });

  it("readStoredStaffTab maps a stored URL segment back to its tab", () => {
    expect(readStoredStaffTab()).toBe("");
    persistStaffTab("x");
    const key = Object.keys(window.localStorage)[0];
    for (const [segment, tab] of [["printing", "machines"], ["machine-service", "machines"], ["to-buy", "tobuy"], ["inventory", "inventory"], ["", ""]] as const) {
      window.localStorage.setItem(key, segment);
      expect(readStoredStaffTab()).toBe(tab);
    }
  });
});
