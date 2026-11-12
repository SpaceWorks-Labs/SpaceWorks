import { describe, expect, it } from "vitest";

import { capabilityOn, FEATURE_DEFINITIONS, INVENTORY_CHILD_FEATURES } from "../../lib/features";
import { moduleKeys } from "../../lib/moduleLabels";
import { RETIRED_FEATURES } from "../../lib/retiredFeatures";
import { sidebarSections } from "./sidebarSections";
import { STAFF_TAB_KEYS } from "./staffAccess";
import { filterTabsByEnabledModules, TAB_FEATURES, TAB_MODULES } from "./staffTabs";

// Module audit 0.12.0: the staff console's module/feature gates, checked against the code's OWN maps
// (TAB_MODULES / TAB_FEATURES) so a tab added to either is covered without editing this file.
const MODULES = moduleKeys() as string[];
const LIVE_FEATURES = FEATURE_DEFINITIONS.map(feature => feature.key).filter(key => !RETIRED_FEATURES.has(key));
const everything = { enabled_modules: MODULES, enabled_features: LIVE_FEATURES };

function sidebarKeys(tabs: readonly string[]) {
  return sidebarSections(tabs, "dashboard")
    .flatMap(section => [...section.items, ...(section.more ?? [])])
    .flatMap(item => [item, ...(item.children ?? [])])
    .map(item => item.key);
}

describe("the tab gate maps name real tabs, modules and features", () => {
  it("every gated tab is a staff tab", () => {
    for (const tab of [...Object.keys(TAB_MODULES), ...Object.keys(TAB_FEATURES)]) expect(STAFF_TAB_KEYS).toContain(tab);
  });

  it("every module a tab needs is a registered module key", () => {
    for (const [tab, modules] of Object.entries(TAB_MODULES)) {
      for (const module of modules) expect(MODULES, `${tab} -> ${module}`).toContain(module);
    }
  });

  it("every switch a tab needs is a live feature key", () => {
    const keys = new Set(FEATURE_DEFINITIONS.map(feature => feature.key));
    for (const [tab, switches] of Object.entries(TAB_FEATURES)) {
      for (const key of switches) {
        expect(keys.has(key), `${tab} -> ${key}`).toBe(true);
        expect(RETIRED_FEATURES.has(key), `${tab} -> retired ${key}`).toBe(false);
      }
    }
  });
});

describe("a module switched off for this space removes its tab, sidebar entry and nothing else", () => {
  const moduleTabs = Object.entries(TAB_MODULES).filter(([tab]) => tab !== "direct");

  it.each(moduleTabs)("%s disappears when all of %j are off", (tab, modules) => {
    const on = filterTabsByEnabledModules(STAFF_TAB_KEYS, everything);
    const offModules = MODULES.filter(key => !modules.includes(key));
    const off = filterTabsByEnabledModules(STAFF_TAB_KEYS, { ...everything, enabled_modules: offModules });
    expect(on).toContain(tab);
    expect(off).not.toContain(tab);
    expect(sidebarKeys(off)).not.toContain(tab);
    // Every other tab that does not depend on the switched-off modules stays.
    const unaffected = on.filter(other => other !== tab && !(TAB_MODULES[other] ?? []).every(key => modules.includes(key)));
    for (const other of unaffected.filter(other => !TAB_FEATURES[other])) expect(off).toContain(other);
  });

  it("the direct-handout tab follows its own switch", () => {
    const off = filterTabsByEnabledModules(STAFF_TAB_KEYS, {
      ...everything, enabled_features: LIVE_FEATURES.filter(key => key !== "inventory.self_checkout"),
    });
    expect(filterTabsByEnabledModules(STAFF_TAB_KEYS, everything)).toContain("direct");
    expect(off).not.toContain("direct");
  });
});

describe("a capability switched off removes the tab only when every switch that serves it is off", () => {
  it.each(Object.entries(TAB_FEATURES))("%s follows %j", (tab, switches) => {
    const allOff = filterTabsByEnabledModules(STAFF_TAB_KEYS, {
      ...everything, enabled_features: LIVE_FEATURES.filter(key => !switches.includes(key)),
    });
    expect(filterTabsByEnabledModules(STAFF_TAB_KEYS, everything)).toContain(tab);
    expect(allOff).not.toContain(tab);
    expect(sidebarKeys(allOff)).not.toContain(tab);
    // One switch is enough to keep a shared tab (a To-Buy list serves both parents).
    const oneOn = filterTabsByEnabledModules(STAFF_TAB_KEYS, {
      ...everything, enabled_features: [...LIVE_FEATURES.filter(key => !switches.includes(key)), switches[0]],
    });
    expect(oneOn).toContain(tab);
  });

  it("a parent module off hides a capability tab even while its stored switch is on", () => {
    const off = filterTabsByEnabledModules(STAFF_TAB_KEYS, {
      ...everything, enabled_modules: MODULES.filter(key => key !== "machines"),
      enabled_features: LIVE_FEATURES.filter(key => key !== "inventory.repairs" && key !== "inventory.issue_reporting"
        && key !== "inventory.maintenance" && !key.startsWith("bookings.")),
    });
    expect(off).not.toContain("repairs");
  });
});

describe("the Inventory master switch (decision 254)", () => {
  it("hides every loan tab and every inventory child switch", () => {
    const off = { ...everything, enabled_features: LIVE_FEATURES.filter(key => key !== "loans.enabled") };
    const tabs = filterTabsByEnabledModules(STAFF_TAB_KEYS, off);
    for (const tab of ["requests", "inventory", "stocktake", "transfers", "containers", "bulk", "qr", "scanner"]) {
      expect(tabs).not.toContain(tab);
    }
    for (const key of INVENTORY_CHILD_FEATURES) expect(capabilityOn(off, key), key).toBe(false);
  });
});

describe("capabilityOn mirrors the server's effective switch", () => {
  it("reads a retired switch as off however it is stored (decision 319)", () => {
    for (const key of RETIRED_FEATURES) {
      expect(capabilityOn({ enabled_modules: MODULES, enabled_features: [key] }, key), key).toBe(false);
    }
  });

  it("reads a child as off while its parent module is off, and on once it is installed", () => {
    const child = FEATURE_DEFINITIONS.find(feature => feature.parent_module === "events" && !RETIRED_FEATURES.has(feature.key));
    expect(child).toBeDefined();
    const key = child!.key;
    expect(capabilityOn({ enabled_modules: MODULES.filter(module => module !== "events"), enabled_features: [key] }, key)).toBe(false);
    expect(capabilityOn({ enabled_modules: ["events"], enabled_features: [key] }, key)).toBe(true);
  });

  it("reads a parentless switch by its own state", () => {
    expect(capabilityOn({ enabled_modules: [], enabled_features: ["safety.incidents"] }, "safety.incidents")).toBe(true);
    expect(capabilityOn({ enabled_modules: MODULES, enabled_features: [] }, "safety.incidents")).toBe(false);
  });
});
