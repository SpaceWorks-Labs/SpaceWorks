import { expect, it } from "vitest";

import { SIDEBAR_SECTIONS, SPACE_MANAGER_SECTIONS } from "./sidebarSections";
import { getStaffAccess, TAB_LABELS } from "./staffAccess";
import { filterTabsByEnabledModules } from "./staffTabs";

it("shows Consumables only while inventory.consumables is on", () => {
  const tabs = getStaffAccess(["view_inventory", "edit_inventory"], false, false).allowedTabs;
  expect(tabs).toContain("consumables");
  const space = { enabled_modules: ["staff_admin"], enabled_features: ["loans.enabled"] };
  expect(filterTabsByEnabledModules(tabs, space)).not.toContain("consumables");
  expect(filterTabsByEnabledModules(tabs, { ...space, enabled_features: ["loans.enabled", "inventory.consumables"] })).toContain("consumables");
});

it("admits machine staff and refuses staff with no inventory or machine reach", () => {
  expect(getStaffAccess(["manage_machines"], false, false).allowedTabs).toContain("consumables");
  expect(getStaffAccess(["manage_events"], false, false).allowedTabs).not.toContain("consumables");
});

it("sits next to To-Buy in both menus with a label", () => {
  expect(TAB_LABELS.consumables).toBe("Consumables");
  for (const sections of [SIDEBAR_SECTIONS, SPACE_MANAGER_SECTIONS]) {
    const inventory = sections.find(section => section.key === "inventory")!;
    expect(inventory.tabs.indexOf("consumables")).toBe(inventory.tabs.indexOf("tobuy") + 1);
  }
});
