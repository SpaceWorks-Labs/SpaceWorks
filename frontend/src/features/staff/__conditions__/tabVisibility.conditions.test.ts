import { describe, expect, it } from "vitest";

import { getStaffAccess, staffLandingTab, STAFF_TAB_KEYS } from "../staffAccess";
import { sidebarSections } from "../sidebarSections";
import { filterTabsByEnabledModules } from "../staffTabs";

// Decision 246 condition matrix (frontend): every staff tab x every role, then module/capability off.
// Roles are the EFFECTIVE actions `/auth/me` sends (role_catalog + rbac.IMPLIED_ACTIONS), as in
// staffAccess.roleMatrix.test.ts. SAs = superadmin inside a space; SA = superadmin with no space.
const SM = ["accept_request", "approve_card_designs", "assign_box", "collect_service_request", "edit_inventory", "issue_direct_loan",
  "issue_request", "manage_bookings", "manage_devices", "manage_events", "manage_id_programmes", "manage_machines", "manage_makerspace",
  "manage_member_cards", "manage_members", "manage_printing", "manage_qr", "manage_shop", "record_payment", "record_reimbursement_payout",
  "reject_request", "return_request", "scan_member_cards", "sell_shop", "upload_evidence", "view_analytics", "view_audit", "view_finance",
  "view_id_programmes", "view_inventory", "view_shop"];
const ROLES: Record<string, { actions: string[]; superadmin: boolean }> = {
  SM: { actions: SM, superadmin: false },
  IM: { actions: ["accept_request", "assign_box", "edit_inventory", "issue_direct_loan", "issue_request", "manage_qr", "reject_request",
    "return_request", "upload_evidence", "view_audit", "view_inventory"], superadmin: false },
  MM: { actions: ["collect_service_request", "manage_machines", "manage_printing"], superadmin: false },
  EM: { actions: ["manage_events"], superadmin: false },
  BM: { actions: ["manage_bookings"], superadmin: false },
  HO: { actions: ["assign_box", "collect_service_request", "issue_direct_loan", "issue_request", "return_request", "upload_evidence",
    "view_inventory"], superadmin: false },
  TE: { actions: ["run_maintenance", "set_service_state", "work_repairs"], superadmin: false },
  SH: { actions: ["manage_shop", "sell_shop", "view_shop"], superadmin: false },
  SA: { actions: [], superadmin: true },
  SAs: { actions: SM, superadmin: true },
  NoRole: { actions: [], superadmin: false },
};
const access = (role: string, singleTenant = false) => getStaffAccess(ROLES[role].actions, ROLES[role].superadmin, singleTenant);

// tab -> roles that may open it (all modules on). One row per tab of STAFF_TAB_KEYS.
const VISIBLE_TO: Record<string, string> = {
  "platform-dashboard": "SA,SAs", "platform-spaces": "SA,SAs", "platform-inbox": "SA,SAs", "platform-access": "SA,SAs", "platform-security": "SA,SAs",
  "platform-data": "SA,SAs", "platform-limits": "SA,SAs", platform: "SA,SAs", "platform-analytics": "SA,SAs", migration: "SA,SAs",
  usage: "SM,SAs", dashboard: "SM,IM,MM,EM,BM,HO,TE,SH,SAs", notifications: "SM,IM,MM,EM,BM,HO,TE,SH,SAs",
  channels: "SM,IM,MM,EM,BM,HO,TE,SH", requests: "SM,IM,HO,SAs", direct: "SM,IM,HO,SAs", handover: "SM,MM,HO,SAs",
  inventory: "SM,IM,SAs", needsfix: "SM,IM,SAs", categories: "SM,IM,SAs", transfers: "SM,IM,SAs", stocktake: "SM,IM,SAs",
  containers: "SM,IM,SAs", ledger: "SM,IM,HO,SAs", bulk: "SM,IM,SAs", qr: "SM,IM,SAs", scanner: "SM,IM,SAs",
  machines: "SM,MM,SAs", events: "SM,EM,SAs", bookings: "SM,BM,SAs", members: "SM,SAs", cards: "SM,SAs",
  tobuy: "SM,IM,MM,SAs", warranty: "SM,IM,MM,SAs", consumables: "SM,IM,MM,SAs", repairs: "SM,IM,MM,BM,TE,SAs",
  reports: "SM,IM,MM,EM,BM,TE,SH,SAs", accountability: "SM,IM,SAs", api: "SM,IM,MM,EM,BM,TE,SH,SAs",
  settings: "SM,SAs", security: "SM,SA,SAs", users: "SM,SA,SAs", modules: "SM,SA,SAs", backups: "SM,SA,SAs",
  emailtemplates: "SM,IM,MM,EM,BM,SAs", audit: "SM,IM,MM,EM,BM,TE,SH,SAs", devices: "SM,SAs", "email-logs": "SM,SAs",
  payments: "SM,IM,MM,EM,BM,HO,SH,SAs", refunds: "SM,IM,MM,EM,BM,SH,SAs", finance: "SM,IM,MM,EM,BM,SH,SAs", exports: "SM,SAs",
  organizations: "SM,IM,MM,EM,BM,TE,SH,SA,SAs,NoRole", organized: "SM,IM,MM,EM,BM,TE,SH,NoRole",
  "organization-analytics": "SM,IM,MM,EM,BM,TE,SH,NoRole", incidents: "SM,IM,MM,EM,BM,SAs", shop: "SM,SH,SAs",
  analytics: "SM,SAs", granted: "",
  // Decisions 242/259: Dashboard also serves TE and SH; Ledger is read-only for HO (IN11); Accountability is read-only
  // for IM (IN8); Payments is every charge owner's own-area queue, the desk's limited to loan charges.
  // Decision 242(k): every role that runs a schedule layer (operations/schedule.available_layers).
  schedule: "SM,IM,MM,EM,BM,TE,SAs",
};

describe("staff tab visibility per role (all modules on)", () => {
  // Donations screens are still being built (lane C-donations): their row is added with that lane.
  const PENDING = ["donations"];
  it("lists every tab key exactly once", () => {
    expect(Object.keys(VISIBLE_TO).sort()).toEqual(STAFF_TAB_KEYS.filter(tab => !PENDING.includes(tab)).sort());
  });

  it.each(Object.entries(VISIBLE_TO))("%s is visible to [%s] and hidden from every other role", (tab, who) => {
    const allowed = who ? who.split(",") : [];
    for (const role of Object.keys(ROLES)) expect(access(role).allowedTabs.includes(tab), `${tab} for ${role}`).toBe(allowed.includes(role));
  });

  it("hides every platform page and the organization group in a single-tenant (custom domain) console", () => {
    for (const role of ["SA", "SAs", "SM", "IM"]) {
      const tabs = access(role, true).allowedTabs;
      for (const tab of ["platform-dashboard", "platform-spaces", "platform", "platform-analytics", "organizations", "organized", "organization-analytics"]) {
        expect(tabs, `${tab} for ${role}`).not.toContain(tab);
      }
    }
  });

  it("opens Assigned resources only for event or booking grants, and only the grant for a roleless holder", () => {
    expect(getStaffAccess([], false, false, false, true).allowedTabs).toEqual(expect.arrayContaining(["granted", "organizations"]));
    expect(getStaffAccess([], false, false, false, false, true).allowedTabs).toContain("granted");
    expect(getStaffAccess([], false, false, false, true).allowedTabs).not.toContain("dashboard");
    expect(getStaffAccess([], false, true, false, true).allowedTabs).toEqual(["granted"]);
    expect(getStaffAccess(ROLES.EM.actions, false, false, false, true).allowedTabs).toContain("granted");
  });

  it("drops the cross-venue pages for someone in no organization", () => {
    const tabs = getStaffAccess(ROLES.IM.actions, false, false, false, false, false, false).allowedTabs;
    for (const tab of ["organizations", "organized", "organization-analytics"]) expect(tabs).not.toContain(tab);
    expect(getStaffAccess([], false, false, false, false, false, false).allowedTabs).toEqual(["organizations"]);
  });
});

// tab -> module(s) that back it (any one on keeps it) and capability switches (any one on keeps it).
const MODULE_OF: [string, string][] = [["notifications", "notifications"], ["machines", "machines"], ["devices", "devices"],
  ["handover", "machine_service"], ["events", "events"], ["bookings", "bookings"], ["cards", "membership"],
  ["transfers", "stock_transfers"], ["stocktake", "stocktake"], ["containers", "containers"], ["bulk", "bulk_import"],
  ["qr", "qr_print_batches"], ["scanner", "scanner"], ["reports", "reports"], ["shop", "shop"], ["analytics", "analytics"]];
const FEATURE_OF: [string, string[]][] = [["tobuy", ["inventory.tobuy", "machines.tobuy"]], ["warranty", ["inventory.warranty", "machines.warranty"]],
  ["consumables", ["inventory.consumables"]], ["repairs", ["inventory.repairs", "machines.repairs", "bookings.room_repairs"]],
  ["incidents", ["safety.incidents"]], ["finance", ["finance.ledger"]]];
const ALL_MODULES = [...new Set([...MODULE_OF.map(([, m]) => m), "public_inventory", "request_workflow", "staff_admin", "membership", "machines"])];
const ALL_FEATURES = ["loans.enabled", "inventory.self_checkout", ...FEATURE_OF.flatMap(([, f]) => f)];
const space = (modules = ALL_MODULES, features = ALL_FEATURES) => ({ enabled_modules: modules, enabled_features: features });
const tabsFor = (role: string, makerspace = space()) =>
  filterTabsByEnabledModules(access(role).allowedTabs, makerspace, ROLES[role].actions);
// The Settings family is collapsed until one of its pages is active, so union over each possible active page.
const FAMILY = ["dashboard", "settings", "security", "modules", "backups", "migration", "api", "emailtemplates"];
const sidebarKeys = (role: string, tabs: readonly string[]) => FAMILY.flatMap(active =>
  sidebarSections(tabs, active, undefined, undefined, access(role).handoutOnly, role === "SM" || role === "SAs")
    .flatMap(section => [...section.items, ...(section.more ?? [])]).flatMap(item => [item, ...(item.children ?? [])]).map(item => item.key));

describe("module off, per role: the tab, its sidebar entry and the landing page follow", () => {
  const roles = Object.keys(ROLES);
  const cases = MODULE_OF.flatMap(([tab, module]) => roles.filter(role => access(role).allowedTabs.includes(tab)).map(role => [role, tab, module] as const));

  it.each(cases)("%s: %s is shown with %s on and gone (tab and sidebar) with it off", (role, tab, module) => {
    expect(tabsFor(role)).toContain(tab);
    const off = tabsFor(role, space(ALL_MODULES.filter(key => key !== module)));
    expect(off).not.toContain(tab);
    expect(sidebarKeys(role, off)).not.toContain(tab);
    expect(off).toContain(staffLandingTab(off) ?? "");
  });

  const featureCases = FEATURE_OF.flatMap(([tab, switches]) => roles.filter(role => access(role).allowedTabs.includes(tab)).map(role => [role, tab, switches] as const));
  it.each(featureCases)("%s: %s disappears when every one of %j is off", (role, tab, switches) => {
    const off = tabsFor(role, space(ALL_MODULES, ALL_FEATURES.filter(key => !switches.includes(key))));
    expect(off).not.toContain(tab);
  });

  it.each(roles.filter(role => access(role).allowedTabs.includes("requests")))("%s: lending off (loans.enabled) removes every loan tab", role => {
    const off = tabsFor(role, space(ALL_MODULES, ALL_FEATURES.filter(key => key !== "loans.enabled")));
    for (const tab of ["requests", "inventory", "ledger", "direct", "needsfix", "qr", "scanner", "stocktake"]) expect(off).not.toContain(tab);
  });

  it.each(roles)("%s: every module-filtered tab has a sidebar entry (nothing reachable only by URL)", role => {
    const tabs = tabsFor(role).filter(tab => !["channels", "granted"].includes(tab));
    const keys = sidebarKeys(role, tabs);
    expect(tabs.filter(tab => !keys.includes(tab))).toEqual([]);
  });

  it("area narrowing: a Booking Manager keeps Repairs only through a booking switch, a Machine Manager only through a machine switch", () => {
    expect(tabsFor("BM", space(ALL_MODULES, ["loans.enabled", "machines.repairs"]))).not.toContain("repairs");
    expect(tabsFor("BM", space(ALL_MODULES, ["loans.enabled", "bookings.room_repairs"]))).toContain("repairs");
    expect(tabsFor("MM", space(ALL_MODULES, ["loans.enabled", "bookings.room_repairs"]))).not.toContain("repairs");
    expect(tabsFor("TE", space(ALL_MODULES, ["loans.enabled", "bookings.room_repairs"]))).toContain("repairs");
  });
});
