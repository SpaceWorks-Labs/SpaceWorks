import { describe, expect, it } from "vitest";

import type { ShellItem, ShellSection } from "../../components/shell";
import { getStaffAccess, STAFF_TAB_KEYS } from "./staffAccess";
import { hubEntries } from "./settingsHubCatalog";
import { SIDEBAR_SECTIONS, SPACE_MANAGER_SECTIONS, sidebarSections } from "./sidebarSections";

const flatten = (items: readonly ShellItem[]): ShellItem[] => items.flatMap(item => [item, ...flatten(item.children ?? [])]);
const keys = (nav: ShellSection[]) => new Set(nav.flatMap(section => flatten([...section.items, ...section.more ?? []]).map(item => item.key)));
// The settings sections MakerspaceSettingsPanel renders for a full-access Space Manager.
const SETTINGS_SECTIONS = ["start", "general", "branding", "features", "lending", "membership", "bookings", "events", "materials", "money", "notifications", "channels", "integrations", "privacy"];

describe("Space Manager menu (task groups)", () => {
  const all = [...STAFF_TAB_KEYS];

  it("lists every tab of the old menu exactly once", () => {
    const old = SIDEBAR_SECTIONS.flatMap(section => [...section.tabs, ...section.more ?? []]).sort();
    const next = SPACE_MANAGER_SECTIONS.flatMap(section => [...section.tabs, ...section.more ?? []]);
    expect([...next].sort()).toEqual(old);
    expect(new Set(next).size).toBe(next.length);
  });

  it("keeps every old destination reachable from the sidebar or the Settings hub", () => {
    // Walk the old nav targets: each one must be a sidebar link (top level, under More, or in
    // the collapsed Settings family once it is opened) or a link on the Settings hub page.
    const collapsed = keys(sidebarSections(all, "dashboard", undefined, undefined, false, true));
    const opened = keys(sidebarSections(all, "settings", undefined, undefined, false, true));
    const hub = new Set(hubEntries(SETTINGS_SECTIONS, all).flatMap(entry => "tab" in entry.target ? [entry.target.tab] : []));
    expect(collapsed.has("settings-family")).toBe(true);
    for (const section of SIDEBAR_SECTIONS) for (const tab of [...section.tabs, ...section.more ?? []]) {
      const reachable = collapsed.has(tab) || opened.has(tab) || (collapsed.has("settings-family") && hub.has(tab));
      expect(reachable, `${tab} is unreachable`).toBe(true);
    }
  });

  it("groups by task, with Staff & roles first under People and less-used items collapsed", () => {
    const access = getStaffAccess(["manage_makerspace", "view_inventory", "edit_inventory", "manage_qr", "manage_machines",
      "manage_events", "manage_bookings", "manage_members", "view_audit", "view_finance", "accept_request", "issue_request",
      "issue_direct_loan", "manage_devices"], false, false);
    const nav = sidebarSections(access.allowedTabs, "dashboard", undefined, undefined, false, true);
    expect(nav.map(section => section.label)).toEqual(["Today", "People", "Inventory & loans", "Machines", "Events", "Bookings", "Shop", "Money", "Insights", "Space settings"]);
    const people = nav.find(section => section.key === "people")!;
    expect(people.items[0]).toMatchObject({ key: "users", label: "Staff & roles" });
    const inventory = nav.find(section => section.key === "inventory")!;
    expect(inventory.more?.map(item => item.key)).toContain("ledger");
    const settings = nav.find(section => section.key === "settings")!;
    expect(settings.items).toHaveLength(1);
    expect(settings.items[0]).toMatchObject({ key: "settings-family", label: "Settings", children: undefined });
  });

  it("opens the Settings family when one of its pages is active", () => {
    const nav = sidebarSections(all, "api", undefined, undefined, false, true);
    const family = nav.find(section => section.key === "settings")!.items[0];
    expect(family.children?.map(item => item.key)).toEqual(["settings", "security", "emailtemplates", "email-logs", "api", "exports", "backups", "usage", "modules", "migration"]);
    expect(family.children?.[0].label).toBe("All settings");
  });

  it("leaves every other role's menu unchanged", () => {
    for (const actions of [["view_inventory", "edit_inventory"], ["manage_events"], ["manage_bookings"], ["manage_machines"]]) {
      const tabs = getStaffAccess(actions, false, false).allowedTabs;
      expect(JSON.stringify(sidebarSections(tabs, "dashboard"))).toEqual(JSON.stringify(sidebarSections(tabs, "dashboard", undefined, undefined, false, false)));
      expect(sidebarSections(tabs, "dashboard").map(section => section.key)).not.toContain("today");
    }
  });
});

describe("superadmin platform menu (SA-4, decision 285)", () => {
  const platformTabs = ["platform-dashboard", "platform-spaces", "platform-access", "platform-inbox", "platform-analytics",
    "platform-limits", "platform-data", "platform-security", "platform"];
  it("uses the /control/ group names in their order, then platform settings", () => {
    const nav = sidebarSections(platformTabs, "platform-dashboard");
    expect(nav.map(section => section.label)).toEqual(["Overview", "Spaces", "People & roles", "Messaging & notifications",
      "Integrations & analytics", "Limits & hosting", "Data & recovery", "Security & audit", "Platform settings"]);
    expect(nav.flatMap(section => section.items.map(item => item.key))).toEqual(platformTabs);
  });
});
