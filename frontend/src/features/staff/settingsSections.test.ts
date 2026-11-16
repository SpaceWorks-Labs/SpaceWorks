import { describe, expect, it } from "vitest";

import type { ShellItem, ShellSection } from "../../components/shell";
import { getStaffAccess } from "./staffAccess";
import { sidebarSections } from "./sidebarSections";
import { keptStaffSubPath, staffPathState, staffTabPath } from "./staffTabs";
import { orderedSettingsSections, settingsGroups, settingsLanding, settingsLinkTarget, settingsSectionAlias, settingsSectionForHash,
  settingsSectionFromSubPath } from "./settingsSections";
import { hubEntries, settingsLinkEntry, settingsSectionHelp } from "./settingsHubCatalog";

// The built-in role catalogue (backend makerspaces/role_catalog.py).
const ROLES: Record<string, string[]> = {
  "Space Manager": ["accept_request", "assign_box", "edit_inventory", "issue_direct_loan", "issue_request", "manage_bookings",
    "manage_events", "manage_devices", "manage_machines", "manage_makerspace", "manage_members", "manage_member_cards",
    "manage_printing", "manage_qr", "record_payment", "record_reimbursement_payout", "reject_request", "return_request",
    "upload_evidence", "view_audit", "view_finance", "view_inventory"],
  "Inventory Manager": ["accept_request", "assign_box", "edit_inventory", "issue_direct_loan", "issue_request", "manage_qr",
    "reject_request", "return_request", "upload_evidence", "view_audit", "view_inventory"],
  "Machine Manager": ["manage_machines"],
  "Event Manager": ["manage_events"],
  "Booking Manager": ["manage_bookings"],
  Handover: ["view_inventory", "assign_box", "issue_request", "issue_direct_loan", "return_request", "upload_evidence", "collect_service_request"],
  Technician: ["work_repairs", "run_maintenance", "set_service_state"],
  "Shop Manager": ["manage_shop", "sell_shop", "view_shop"],
  Member: [],
};
const flatten = (items: readonly ShellItem[]): ShellItem[] => items.flatMap(item => [item, ...flatten(item.children ?? [])]);
const keys = (nav: ShellSection[]) => nav.flatMap(section => flatten([...section.items, ...section.more ?? []]).map(item => item.key));

describe("settings subpage routes", () => {
  it("builds and reads /admin/settings/<section> in both route shapes", () => {
    expect(staffTabPath("settings", false, null, false, "lending")).toBe("/admin/settings/lending");
    expect(staffTabPath("settings", false, "forge", false, "lending")).toBe("/m/forge/admin/settings/lending");
    expect(staffTabPath("settings", false, "forge", true, "lending")).toBe("/admin/settings/lending");
    expect(staffPathState("/m/forge/admin/settings/money", false)).toEqual({ makerspaceSlug: "forge", tab: "settings", subPath: "money" });
  });

  it("keeps the section through StaffWorkspace canonicalization only on the settings tab", () => {
    expect(keptStaffSubPath("settings", "settings", "health")).toBe("health");
    expect(keptStaffSubPath("settings", "dashboard", "health")).toBe("");
  });

  it("orders sections by group, lands on the first and resolves old anchors", () => {
    const available = ["money", "general", "overview", "health", "lending"];
    expect(orderedSettingsSections(available)).toEqual(["overview", "general", "lending", "money", "health"]);
    expect(settingsLanding(available)).toBe("overview");
    expect(settingsLanding(["money", "general"])).toBe("general");
    expect(settingsSectionForHash("#money", available)).toBe("money");
    expect(settingsSectionForHash("#start", available)).toBe("overview");
    expect(settingsSectionForHash("#bookings", available)).toBe("");
    expect(settingsSectionForHash("", available)).toBe("");
    expect(settingsSectionFromSubPath("lending/extra")).toBe("lending");
  });

  it("files every section in exactly one group, in the owner's order (decision 255)", () => {
    const all = settingsGroups().flatMap(group => group.items);
    expect(new Set(all).size).toBe(all.length);
    expect(settingsGroups().map(group => group.key)).toEqual(["space", "people", "areas", "money", "communication", "integrations", "administration"]);
    expect(settingsGroups().find(group => group.key === "areas")?.items.filter(id => !id.startsWith("tab:")))
      .toEqual(["features", "lending", "materials", "events", "bookings"]);
  });

  it("gives every page and every console link a title and one line of help", () => {
    for (const item of settingsGroups().flatMap(group => group.items)) {
      if (item === "overview") continue;
      const help = settingsLinkTarget(item) ? settingsLinkEntry(item)?.description : settingsSectionHelp(item);
      expect(help, item).toMatch(/\S.+\.$/);
    }
  });

  it("reads console links and retired pages", () => {
    expect(settingsLinkTarget("tab:shop/settings")).toEqual({ tab: "shop", view: "settings" });
    expect(settingsLinkTarget("tab:users")).toEqual({ tab: "users", view: "" });
    expect(settingsLinkTarget("lending")).toBeNull();
    expect(settingsSectionAlias("tools")).toBe("overview");
    expect(settingsSectionAlias("lending")).toBe("");
    expect(settingsSectionForHash("#tools", ["overview"])).toBe("overview");
  });

  it("searches settings that live on console views and opens them on that view", () => {
    const targets = hubEntries([], ["shop", "donations"]).map(entry => entry.target);
    expect(targets).toEqual([{ tab: "shop", view: "settings" }, { tab: "donations", view: "profile" }]);
  });
});

describe("settings visibility per role", () => {
  it("opens Makerspace settings only for the Space Manager and a superadmin working in the space", () => {
    for (const [role, actions] of Object.entries(ROLES)) {
      expect(getStaffAccess(actions, false, false).allowedTabs.includes("settings"), role).toBe(role === "Space Manager");
    }
    expect(getStaffAccess(ROLES["Space Manager"], true, false).allowedTabs).toContain("settings");
    // Before choosing a space the superadmin sees the platform surface, not space settings.
    expect(getStaffAccess([], true, false).allowedTabs).not.toContain("settings");
  });

  it("keeps the Space Manager's collapsed Settings family", () => {
    const tabs = getStaffAccess(ROLES["Space Manager"], false, false).allowedTabs;
    const nav = sidebarSections(tabs, "dashboard", undefined, undefined, false, true);
    expect(nav.find(section => section.key === "settings")?.items[0]).toMatchObject({ key: "settings-family", label: "Settings" });
  });

  it.each(["Inventory Manager", "Machine Manager", "Event Manager", "Booking Manager", "Technician", "Shop Manager"])(
    "shows the %s their tool pages flat, not a Settings button they cannot use", role => {
      const tabs = getStaffAccess(ROLES[role], false, false).allowedTabs;
      const nav = sidebarSections(tabs, "dashboard");
      const tools = nav.find(section => section.key === "settings")!;
      expect(tools.label).toBe("Tools");
      expect(keys(nav)).not.toContain("settings-family");
      expect(keys(nav)).not.toContain("settings");
      expect(tools.items.map(item => item.key)).toContain("api");
    });

  it("gives handover staff and members no settings at all", () => {
    const handover = getStaffAccess(ROLES.Handover, false, false);
    expect(keys(sidebarSections(handover.allowedTabs, "dashboard", undefined, undefined, handover.handoutOnly))).not.toContain("api");
    // Role-screen audit 0.12.0: an organization member also reaches the organizer pages the server serves them.
    expect(getStaffAccess(ROLES.Member, false, false).allowedTabs).toEqual(["organizations", "organized", "organization-analytics"]);
    expect(getStaffAccess(ROLES.Member, false, false, false, false, false, false).allowedTabs).toEqual(["organizations"]);
  });
});
