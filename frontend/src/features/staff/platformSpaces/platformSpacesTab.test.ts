import { describe, expect, it } from "vitest";
import { getStaffAccess } from "../staffAccess";
import { sidebarSections } from "../sidebarSections";
import { staffTabPath } from "../staffTabs";

describe("the Spaces platform tab", () => {
  it("belongs to the superadmin only, and never on a single-tenant deployment", () => {
    expect(getStaffAccess([], true, false).allowedTabs).toContain("platform-spaces");
    expect(getStaffAccess(["manage_makerspace"], true, false).allowedTabs).toContain("platform-spaces");
    expect(getStaffAccess([], true, true).allowedTabs).not.toContain("platform-spaces");
    expect(getStaffAccess(["manage_makerspace"], false, false).allowedTabs).not.toContain("platform-spaces");
  });

  it("is a global tab next to the platform dashboard", () => {
    expect(staffTabPath("platform-spaces", false, "north-lab")).toBe("/admin/platform-spaces");
    const nav = sidebarSections(["platform-dashboard", "platform-spaces", "platform"], "platform-spaces");
    // SA-4 (decision 285): one heading per /control/ group, named as there.
    expect(nav.find(section => section.key === "platform:overview")?.items.map(item => item.key)).toEqual(["platform-dashboard"]);
    const spaces = nav.find(section => section.key === "platform:spaces");
    expect(spaces?.label).toBe("Spaces");
    expect(spaces?.items.map(item => item.key)).toEqual(["platform-spaces"]);
    expect(spaces?.items[0].label).toBe("Spaces");
    // 0.12.0: the settings-like platform pages sit in their own section.
    expect(nav.find(section => section.key === "platform:settings")?.items.map(item => item.key)).toEqual(["platform"]);
  });
});
