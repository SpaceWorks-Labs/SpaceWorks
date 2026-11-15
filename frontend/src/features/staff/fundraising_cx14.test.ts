import { describe, expect, it } from "vitest";

import { capabilityOn, FEATURE_DEFINITIONS } from "../../lib/features";
import { getStaffAccess, staffLandingTab, TAB_LABELS } from "./staffAccess";
import { filterTabsByEnabledModules } from "./staffTabs";

describe("decision 550: Fundraising navigation and the combined switch", () => {
  it.each([false, true])("shows exactly one area in a tenant console (locked=%s)", locked => {
    const access = getStaffAccess(["manage_donations"], false, locked);
    expect(access.allowedTabs).toEqual(["donations"]);
    expect(access.defaultTab).toBe("donations");
    expect(TAB_LABELS.donations).toBe("Fundraising");
  });

  it("hides the whole area while off and restores it without clearing sponsor preferences", () => {
    const actions = ["manage_donations"];
    const access = getStaffAccess(actions, false, false);
    const off = { enabled_modules: [], enabled_features: ["finance.sponsors"] };
    expect(capabilityOn(off, "finance.sponsors")).toBe(false);
    expect(filterTabsByEnabledModules(access.allowedTabs, off, actions)).toEqual([]);
    const on = { ...off, enabled_features: [...off.enabled_features, "finance.donations"] };
    const tabs = filterTabsByEnabledModules(access.allowedTabs, on, actions);
    expect(tabs).toEqual(["donations"]);
    expect(staffLandingTab(tabs)).toBe("donations");
    expect(capabilityOn(on, "finance.sponsors")).toBe(true);
    expect(off.enabled_features).toEqual(["finance.sponsors"]);
  });

  it("gives the Space Manager the switch and preserves explicitly combined role authority", () => {
    const manager = getStaffAccess(["manage_makerspace", "manage_donations"], false, false);
    expect(manager.allowedTabs).toContain("modules");
    expect(getStaffAccess(["manage_donations"], false, false).allowedTabs).not.toContain("modules");
    expect(FEATURE_DEFINITIONS.find(row => row.key === "finance.donations")?.label).toBe("Donations and sponsors");
    const combined = getStaffAccess(["manage_donations", "manage_events"], false, false);
    expect(combined.allowedTabs).toContain("events");
    expect(combined.allowedTabs).toContain("donations");
    expect(combined.allowedTabs).not.toContain("settings");
  });
});
