import { describe, expect, it } from "vitest";

import { getStaffAccess } from "./staffAccess";
import { staffTabPath, tabFromStaffPath } from "./staffTabs";


describe("organization governance", () => {
  it("gives a governance-only central actor one global workspace", () => {
    const access = getStaffAccess([], false, false);

    // Role-screen audit 0.12.0: plus the cross-venue organizer pages (OrganizedEventListView is IsActiveStaff).
    expect(access.allowedTabs).toEqual(["organizations", "organized", "organization-analytics"]);
    expect(access.defaultTab).toBe("organizations");
    expect(staffTabPath("organizations", false, "forge")).toBe("/admin/organizations");
    expect(tabFromStaffPath("/admin/organizations", false)).toBe("organizations");
  });

  it("does not expose global organization governance on a tenant-locked origin", () => {
    expect(getStaffAccess([], false, true).allowedTabs).not.toContain("organizations");
    expect(getStaffAccess([], true, true).allowedTabs).not.toContain("organizations");
  });
});
