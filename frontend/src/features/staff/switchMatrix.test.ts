import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { FEATURE_DEFINITIONS } from "../../lib/features";
import { RETIRED_FEATURES } from "../../lib/retiredFeatures";
import { memberTabs } from "../members/MemberPortalTabs";
import { sidebarSections } from "./sidebarSections";
import { STAFF_TAB_KEYS } from "./staffAccess";
import { filterTabsByEnabledModules, TAB_FEATURES, TAB_MODULES } from "./staffTabs";

// SWITCH-MATRIX: generated from the module catalogue (generated ModulesEnum) and the tab maps, so a new module key
// or gated tab is covered with no edit here. Off removes the entry everywhere (decision 218); on again restores it.
const api = readFileSync(join(process.cwd(), "src", "generated", "api.ts"), "utf8");
const MODULES = [...(/export type ModulesEnum = ([^;]+);/.exec(api)?.[1] ?? "").matchAll(/"([a-z_]+)"/g)].map((m) => m[1]);
const FEATURES = FEATURE_DEFINITIONS.map((f) => f.key).filter((key) => !RETIRED_FEATURES.has(key));
const CORE = ["staff_admin", "public_inventory", "request_workflow", "scanner", "qr_management", "evidence_uploads"];
const OPTIONAL = MODULES.filter((k) => !CORE.includes(k));
const everything = { enabled_modules: MODULES, enabled_features: FEATURES };

function sidebarKeys(tabs: readonly string[]) {
  return sidebarSections(tabs, "dashboard")
    .flatMap((section) => [...section.items, ...(section.more ?? [])])
    .flatMap((item) => [item, ...(item.children ?? [])])
    .map((item) => item.key);
}

describe("every module key", () => {
  it("is known and the gates name real keys", () => {
    expect(MODULES.length).toBeGreaterThanOrEqual(30);
    for (const required of Object.values(TAB_MODULES).flat()) expect(MODULES, required).toContain(required);
  });

  it.each(OPTIONAL)("%s off: each tab it alone owns leaves the tabs and the sidebar, and returns when on", (module) => {
    const owned = Object.entries(TAB_MODULES).filter(([, keys]) => keys.length === 1 && keys[0] === module).map(([tab]) => tab);
    const on = filterTabsByEnabledModules(STAFF_TAB_KEYS, everything);
    const off = filterTabsByEnabledModules(STAFF_TAB_KEYS, { ...everything, enabled_modules: MODULES.filter((k) => k !== module) });
    const back = filterTabsByEnabledModules(STAFF_TAB_KEYS, everything);
    for (const tab of owned) {
      expect(on, tab).toContain(tab);
      expect(off, tab).not.toContain(tab);
      expect(sidebarKeys(off), tab).not.toContain(tab);
    }
    expect(back).toEqual(on);
    // Nothing the module does not own disappears with it.
    const lost = on.filter((tab) => !off.includes(tab));
    for (const tab of lost) expect(TAB_MODULES[tab] ?? [], tab).toContain(module);
  });

  it("core only: no tab of any optional module survives and the console still has a landing page", () => {
    const core = filterTabsByEnabledModules(STAFF_TAB_KEYS, { enabled_modules: CORE, enabled_features: [] });
    for (const [tab, keys] of Object.entries(TAB_MODULES)) {
      if (!keys.some((k) => CORE.includes(k))) expect(core, tab).not.toContain(tab);
    }
    expect(core).toContain("dashboard");
  });

  it("every module off leaves the member area with its overview and no area tab", () => {
    const tabs = memberTabs([], []);
    expect(tabs).toContain("overview");
    for (const area of ["loans", "events", "bookings"]) expect(tabs).not.toContain(area);
  });
});

describe("every gated capability tab", () => {
  it.each(Object.entries(TAB_FEATURES))("%s hides when all of %j are off and returns when any is on", (tab, keys) => {
    const off = filterTabsByEnabledModules(STAFF_TAB_KEYS, { enabled_modules: MODULES, enabled_features: FEATURES.filter((k) => !keys.includes(k)) });
    expect(off).not.toContain(tab);
    expect(sidebarKeys(off)).not.toContain(tab);
    for (const key of keys) {
      const parent = FEATURE_DEFINITIONS.find((f) => f.key === key)?.parent_module;
      if (RETIRED_FEATURES.has(key) || (parent && !MODULES.includes(parent))) continue;
      const one = filterTabsByEnabledModules(STAFF_TAB_KEYS, { enabled_modules: MODULES, enabled_features: [...FEATURES.filter((k) => !keys.includes(k)), key, "loans.enabled"] });
      if (STAFF_TAB_KEYS.includes(tab)) expect(one, `${tab} via ${key}`).toContain(tab);
    }
  });

  it("a capability whose parent module is off is off, whatever is stored", () => {
    for (const def of FEATURE_DEFINITIONS) {
      if (!def.parent_module) continue;
      const tabs = Object.entries(TAB_FEATURES).filter(([, keys]) => keys.length === 1 && keys[0] === def.key).map(([tab]) => tab);
      for (const tab of tabs) {
        const off = filterTabsByEnabledModules(STAFF_TAB_KEYS, { enabled_modules: MODULES.filter((k) => k !== def.parent_module), enabled_features: FEATURES });
        expect(off, tab).not.toContain(tab);
      }
    }
  });
});
