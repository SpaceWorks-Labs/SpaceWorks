import { beforeEach, describe, expect, it } from "vitest";
import { fireEvent, screen, within } from "@testing-library/react";
import { setRouteSessionContext } from "../../lib/api/sessionContext";
import { getStaffAccess } from "./staffAccess";
import { SIDEBAR_SECTIONS, SPACE_MANAGER_SECTIONS, sidebarSections } from "./sidebarSections";
import { handout, manager, renderWorkspace, resetShellMocks, user } from "../../../e2e/fixtures/staffShellHarness";

const ORG_TABS = ["organizations", "organized", "organization-analytics"];

beforeEach(() => { setRouteSessionContext("person"); resetShellMocks(); });

describe("Organizations group visibility (0.12.0 row 9)", () => {
  it("hides the cross-venue group for staff with no organization", () => {
    const tabs = getStaffAccess(["edit_inventory", "view_inventory"], false, false, false, false, false, false).allowedTabs;
    for (const tab of ORG_TABS) expect(tabs).not.toContain(tab);
    expect(tabs).toContain("inventory");
  });

  it("shows it to staff who belong to an organization, and when the payload has no flag", () => {
    for (const flag of [true, undefined]) {
      const tabs = getStaffAccess(["edit_inventory"], false, false, false, false, false, flag).allowedTabs;
      for (const tab of ORG_TABS) expect(tabs).toContain(tab);
    }
  });

  it("keeps Organizations for the superadmin, whose payload flag is always false", () => {
    expect(getStaffAccess([], true, false, false, false, false, false).allowedTabs).toContain("organizations");
    expect(getStaffAccess(manager, true, false, false, false, false, false).allowedTabs).toContain("organizations");
  });

  it("drops Organizations from a grant-only console without an organization", () => {
    expect(getStaffAccess([], false, false, false, true, false, false).allowedTabs).toEqual(["granted"]);
    expect(getStaffAccess([], false, false, false, true, false, true).allowedTabs).toEqual(["granted", "organizations", "organized", "organization-analytics"]);
  });

  it("removes the group from the rendered sidebar", () => {
    renderWorkspace("/m/lab/admin/dashboard", { actions: ["manage_events"], user: user({ has_organizations: false }) });
    const nav = within(screen.getByRole("navigation", { name: "Staff sections" }));
    expect(nav.queryByRole("link", { name: "Organizations" })).toBeNull();
    expect(nav.queryByRole("link", { name: "Organized events" })).toBeNull();
  });
});

describe("My channels placement (0.12.0 row 10)", () => {
  it("is no longer a sidebar destination", () => {
    for (const section of [...SIDEBAR_SECTIONS, ...SPACE_MANAGER_SECTIONS]) expect([...section.tabs, ...section.more ?? []]).not.toContain("channels");
    const flat = sidebarSections(["dashboard", "notifications", "channels"], "dashboard", undefined, undefined, true);
    expect(flat[0].items.map(item => item.key)).toEqual(["dashboard", "notifications"]);
  });

  it("opens from the account menu", () => {
    renderWorkspace("/m/lab/admin/dashboard", { actions: handout });
    fireEvent.click(screen.getAllByRole("button", { name: /manager/ })[0]);
    expect(screen.getByRole("link", { name: "My notification channels" })).toHaveAttribute("href", "/m/lab/admin/channels");
  });
});
