import { describe, expect, it } from "vitest";
import { getStaffAccess, TAB_LABELS } from "./staffAccess";
import { filterTabsByEnabledModules, staffTabPath, tabFromStaffPath } from "./staffTabs";

describe("Devices tab matches the identity API authority available in lane 7a", () => {
  it.each([[], ["manage_machines"], ["manage_qr"], ["manage_makerspace"], ["manage_machines", "manage_qr"]].map((actions) => ({ actions })))("withholds identity UI from $actions", ({ actions }) => {
    expect(getStaffAccess(actions, false, false).allowedTabs).not.toContain("devices");
  });
  it("admits tenant MANAGE_DEVICES and withholds tenant devices from platform accounts", () => {
    expect(getStaffAccess(["manage_devices"], false, false).allowedTabs).toContain("devices");
    expect(getStaffAccess(["manage_devices"], false, false).allowedTabs).toContain("emailtemplates");
    expect(getStaffAccess([], true, false).allowedTabs).not.toContain("devices");
    expect(TAB_LABELS.devices).toBe("Devices");
  });
  // Skipped 0.12.0: TAB_GROUPS removed (open item B6); kept per decision 244.
  it.skip("places Devices in the Machines group", () => {
    const TAB_GROUPS: { label: string; tabs: string[] }[] = [];
    expect(TAB_GROUPS.find((g) => g.label === "Machines")?.tabs).toContain("devices");
  });
  it("is module gated and has stable scoped/unscoped routes", () => {
    expect(filterTabsByEnabledModules(["devices"], { enabled_modules: [] })).toEqual([]);
    expect(filterTabsByEnabledModules(["devices"], { enabled_modules: ["devices"] })).toEqual(["devices"]);
    expect(staffTabPath("devices", false)).toBe("/admin/devices");
    expect(tabFromStaffPath("/m/forge/admin/devices", false)).toBe("devices");
  });
});
