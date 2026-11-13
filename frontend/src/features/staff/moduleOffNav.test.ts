import { describe, expect, it } from "vitest";

import { memberTabs } from "../members/MemberPortalTabs";
import { sidebarSections } from "./sidebarSections";
import { STAFF_TAB_KEYS } from "./staffAccess";
import { filterTabsByEnabledModules } from "./staffTabs";

// #183B: a module or capability that is off leaves no nav, menu or tab entry behind.
const MODULES = [
  "public_inventory", "request_workflow", "staff_admin", "scanner", "evidence_uploads", "qr_management",
  "notifications", "machines", "devices", "machine_service", "events", "bookings", "membership",
  "stock_transfers", "stocktake", "containers", "bulk_import", "qr_print_batches", "reports", "shop", "analytics",
  "presence", "payments",
];
const FEATURES = [
  "loans.enabled", "inventory.self_checkout", "inventory.tobuy", "machines.tobuy", "inventory.warranty",
  "machines.warranty", "finance.ledger", "inventory.consumables", "machines.repairs", "inventory.repairs",
];
const everything = { enabled_modules: MODULES, enabled_features: FEATURES };

function sidebarKeys(tabs: readonly string[]) {
  return sidebarSections(tabs, "dashboard")
    .flatMap(section => [...section.items, ...(section.more ?? [])])
    .flatMap(item => [item, ...(item.children ?? [])])
    .map(item => item.key);
}

// The staff tabs each module owns; staffTabs.TAB_MODULES is the code's own copy of this.
const MODULE_TABS: Record<string, string[]> = {
  notifications: ["notifications"], machines: ["machines"], devices: ["devices"], machine_service: ["handover"],
  events: ["events"], bookings: ["bookings"], membership: ["cards"], stock_transfers: ["transfers"],
  stocktake: ["stocktake"], containers: ["containers"], bulk_import: ["bulk"], qr_print_batches: ["qr"],
  scanner: ["scanner"], reports: ["reports"], shop: ["shop"],
};

describe("staff navigation with one module off", () => {
  it.each(Object.entries(MODULE_TABS))("%s off hides %j from the tabs and the sidebar", (module, tabs) => {
    const on = filterTabsByEnabledModules(STAFF_TAB_KEYS, everything);
    const off = filterTabsByEnabledModules(STAFF_TAB_KEYS, { ...everything, enabled_modules: MODULES.filter(key => key !== module) });
    for (const tab of tabs) {
      expect(on).toContain(tab);
      expect(off).not.toContain(tab);
      expect(sidebarKeys(off)).not.toContain(tab);
    }
  });

  it.each([
    ["tobuy", ["inventory.tobuy", "machines.tobuy"]],
    ["warranty", ["inventory.warranty", "machines.warranty"]],
    ["consumables", ["inventory.consumables"]],
    ["finance", ["finance.ledger"]],
    ["repairs", ["machines.repairs", "inventory.repairs"]],
  ])("capability-gated tab %s disappears with its switches off", (tab, switches) => {
    const off = filterTabsByEnabledModules(STAFF_TAB_KEYS, {
      ...everything, enabled_features: FEATURES.filter(key => !switches.includes(key)),
    });
    expect(filterTabsByEnabledModules(STAFF_TAB_KEYS, everything)).toContain(tab);
    expect(off).not.toContain(tab);
    expect(sidebarKeys(off)).not.toContain(tab);
  });

  it("lending off hides every loan tab", () => {
    const off = filterTabsByEnabledModules(STAFF_TAB_KEYS, {
      ...everything, enabled_features: FEATURES.filter(key => key !== "loans.enabled"),
    });
    for (const tab of ["requests", "inventory", "direct", "ledger", "accountability"]) expect(off).not.toContain(tab);
  });
});

describe("member portal tabs with a module off", () => {
  const all = ["membership", "request_workflow", "bookings", "events", "notifications"];
  it.each([
    ["bookings", ["bookings"]],
    ["events", ["events"]],
    ["notifications", ["inbox"]],
    ["membership", ["loans", "events", "inbox"]],
  ])("%s off hides %j", (module, tabs) => {
    expect(memberTabs(all)).toEqual(expect.arrayContaining(tabs));
    const off = memberTabs(all.filter(key => key !== module));
    for (const tab of tabs) expect(off).not.toContain(tab);
  });
});
