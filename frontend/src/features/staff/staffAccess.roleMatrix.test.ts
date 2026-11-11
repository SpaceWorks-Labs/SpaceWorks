import { describe, expect, it } from "vitest";

import type { ShellSection } from "../../components/shell";
import { getStaffAccess, staffLandingTab } from "./staffAccess";
import { sidebarSections } from "./sidebarSections";
import { filterTabsByEnabledModules } from "./staffTabs";
import { dashboardDestination } from "./panels/dashboardLinks";

// Decision 217 (2026-11-09): the console each fixed built-in role gets, from the EXPANDED
// actions `/auth/me` sends (role_catalog grants plus rbac IMPLIED_ACTIONS). Module and
// capability switches are applied later by `filterTabsByEnabledModules`; this pins
// permissions only, in a multi-space deployment.
const ROLE_ACTIONS: Record<string, string[]> = {
  space_manager: ["accept_request", "approve_card_designs", "assign_box", "collect_service_request", "edit_inventory",
    "issue_direct_loan", "issue_request", "manage_bookings", "manage_devices", "manage_donations", "manage_events", "manage_id_programmes",
    "manage_machines", "manage_makerspace", "manage_member_cards", "manage_member_units", "manage_members", "manage_printing", "manage_qr",
    "manage_shop", "record_payment", "record_reimbursement_payout", "reject_request", "return_request",
    "scan_member_cards", "sell_shop", "upload_evidence", "view_analytics", "view_audit", "view_finance",
    "view_id_programmes", "view_inventory", "view_member_units", "view_shop"],
  inventory_manager: ["accept_request", "assign_box", "edit_inventory", "issue_direct_loan", "issue_request", "manage_qr",
    "reject_request", "return_request", "upload_evidence", "view_audit", "view_inventory"],
  machine_manager: ["collect_service_request", "manage_machines", "manage_printing"],
  event_manager: ["manage_events"],
  booking_manager: ["manage_bookings"],
  handover: ["assign_box", "collect_service_request", "issue_direct_loan", "issue_request", "return_request",
    "upload_evidence", "view_inventory"],
  technician: ["run_maintenance", "set_service_state", "work_repairs"],
  shop_manager: ["manage_shop", "sell_shop", "view_shop"],
  // Decision 242(m): donations only.
  fundraising: ["manage_donations"],
};
// Person-scoped tabs every staff role gets (own inbox/channels, organization governance, API requests).
const PERSONAL = ["notifications", "channels", "organized", "organization-analytics", "organizations", "api"];

const EXPECTED: Record<string, { landing: string; tabs: string[] }> = {
  inventory_manager: { landing: "dashboard", tabs: ["dashboard", "requests", "direct", "inventory", "needsfix", "categories",
    "tobuy", "transfers", "stocktake", "containers", "ledger", "reports", "warranty", "bulk", "qr",
    "scanner", "emailtemplates", "audit", "refunds", "finance", "consumables", "repairs", "incidents", "schedule", "payments", "accountability"] },
  machine_manager: { landing: "dashboard", tabs: ["dashboard", "handover", "machines", "tobuy", "reports", "warranty",
    "emailtemplates", "refunds", "finance", "consumables", "repairs", "audit", "incidents", "schedule", "payments"] },
  event_manager: { landing: "dashboard", tabs: ["dashboard", "events", "reports", "emailtemplates", "payments", "refunds", "finance", "audit", "incidents", "schedule"] },
  booking_manager: { landing: "dashboard", tabs: ["dashboard", "bookings", "reports", "emailtemplates", "payments", "refunds", "finance", "repairs", "audit", "incidents", "schedule"] },
  // Decision 242(i): the dashboard now serves the Technician and the Shop Manager, so they land on it.
  // Decision 242(a): every charge owner (not the Technician) gets their own-area Payments queue.
  technician: { landing: "dashboard", tabs: ["dashboard", "reports", "repairs", "audit", "schedule"] },
  shop_manager: { landing: "dashboard", tabs: ["dashboard", "reports", "payments", "refunds", "finance", "shop", "audit"] },
  fundraising: { landing: "donations", tabs: ["reports", "refunds", "donations", "audit"] },
};

// #219(e-1): area roles open the Audit tab without view_audit (the server narrows rows to
// their area); timelines and verification still need view_audit. Decision 224(a): the
// accountability page is the people area's (manage_members), so view_audit alone no longer opens it.
const tabsFor = (role: string) => getStaffAccess(ROLE_ACTIONS[role], false, false);

describe("decision 217: per-role console", () => {
  it.each(Object.keys(EXPECTED))("%s gets exactly its job's tabs and landing", role => {
    const access = tabsFor(role);
    expect([...access.allowedTabs].sort()).toEqual([...EXPECTED[role].tabs, ...PERSONAL].sort());
    expect(access.defaultTab).toBe(EXPECTED[role].landing);
    expect(access.handoutOnly).toBe(false);
  });

  it("opens the area audit log without view_audit, and keeps view_audit-only tabs closed", () => {
    for (const role of ["machine_manager", "event_manager", "booking_manager", "technician", "shop_manager"]) {
      const access = tabsFor(role);
      expect(access.canReadAuditLog, role).toBe(true);
      expect(access.canViewAudit, role).toBe(false);
      expect(access.allowedTabs, role).not.toContain("accountability");
    }
    expect(tabsFor("handover").canReadAuditLog).toBe(false);
  });

  it("opens Accountability with manage_members, read-only for the Inventory Manager (decisions 224 a, 248), never on view_audit alone", () => {
    expect(tabsFor("inventory_manager").canViewAudit).toBe(true);
    expect(tabsFor("inventory_manager").allowedTabs).toContain("accountability");
    expect(tabsFor("handover").allowedTabs).not.toContain("accountability");
    expect(tabsFor("space_manager").allowedTabs).toContain("accountability");
    expect(getStaffAccess(["manage_members"], false, false).allowedTabs).toContain("accountability");
    expect(getStaffAccess(["view_audit"], false, false).allowedTabs).not.toContain("accountability");
  });

  // Final audit 0.12.0: retargeting Accountability to manage_members must not drop the lending
  // area's own dashboard tiles. Overdue loans open the ledger, problem reports the repair desk.
  it("points the Inventory Manager's lending tiles at tabs it can open", () => {
    const access = tabsFor("inventory_manager");
    expect(dashboardDestination("overdue_loans").tab).toBe("ledger");
    expect(dashboardDestination("open_problem_reports").tab).toBe("needsfix");
    for (const key of ["overdue_loans", "open_problem_reports", "pending_requests", "awaiting_issue", "low_stock"]) {
      expect(access.allowedTabs, key).toContain(dashboardDestination(key).tab);
    }
    expect(tabsFor("space_manager").allowedTabs).toEqual(expect.arrayContaining(["ledger", "needsfix"]));
  });

  it("keeps Reports and Accountability off a handout-only desk; the Ledger is read-only there (IN11)", () => {
    for (const actions of [ROLE_ACTIONS.handover, [...ROLE_ACTIONS.handover, "record_payment"]]) {
      const access = getStaffAccess(actions, false, false);
      expect(access.handoutOnly).toBe(true);
      expect(access.allowedTabs).toContain("ledger");
      for (const tab of ["reports", "accountability", "audit"]) expect(access.allowedTabs).not.toContain(tab);
    }
  });

  it("keeps Handover on the narrow counter console", () => {
    const access = tabsFor("handover");
    expect(access.handoutOnly).toBe(true);
    expect(access.allowedTabs).toEqual(["dashboard", "requests", "direct", "handover", "payments", "notifications", "channels", "ledger"]);
    expect(access.defaultTab).toBe("dashboard");
  });

  it("gives the Space Manager every space tab, landing on the dashboard", () => {
    const access = tabsFor("space_manager");
    for (const tab of ["settings", "security", "users", "members", "payments", "finance", "refunds", "reports", "accountability", "shop",
      "repairs", "devices", "analytics", "modules", "exports", "backups", "donations"]) expect(access.allowedTabs).toContain(tab);
    expect(access.allowedTabs).not.toContain("migration");
    expect(access.defaultTab).toBe("dashboard");
  });

  it("never opens money, staff, settings or security tabs to an area role", () => {
    for (const role of Object.keys(EXPECTED)) {
      const tabs = tabsFor(role).allowedTabs;
      for (const tab of ["settings", "security", "users", "members", "modules", "exports", "backups", "devices", "usage"]) {
        expect(tabs, `${role} ${tab}`).not.toContain(tab);
      }
      // Decision 242(a): Payments is the own-area queue for every charge owner; the Technician and
      // Fundraising own no area charge (donations stay finance money).
      if (["technician", "fundraising"].includes(role)) expect(tabs, role).not.toContain("payments");
    }
  });

  it("falls back from a module-hidden home by the same landing order", () => {
    expect(staffLandingTab(["notifications", "channels", "shop", "repairs"])).toBe("shop");
    expect(staffLandingTab(["notifications", "repairs"])).toBe("repairs");
    expect(staffLandingTab(["notifications", "channels"])).toBe("notifications");
    expect(staffLandingTab([])).toBeUndefined();
  });
});

// Role-screen audit 0.12.0 (owner: "each role sees only what they manage"). The console a
// role actually gets once module and capability switches are applied, its landing page,
// its sidebar headings, and the out-of-area destinations that must stay absent.
const MODULES = ["public_inventory", "request_workflow", "staff_admin", "scanner", "qr_management", "evidence_uploads",
  "notifications", "printing", "machines", "devices", "machine_service", "events", "bookings", "membership",
  "stock_transfers", "stocktake", "containers", "bulk_import", "qr_print_batches", "reports", "shop", "analytics"];
const FEATURES = ["loans.enabled", "inventory.self_checkout", "inventory.tobuy", "machines.tobuy", "inventory.warranty",
  "machines.warranty", "finance.ledger", "inventory.consumables", "machines.repairs", "inventory.repairs",
  "bookings.room_repairs", "safety.incidents"];
type Space = { enabled_modules: string[]; enabled_features: string[] };
const everything: Space = { enabled_modules: MODULES, enabled_features: FEATURES };
const without = (modules: string[] = [], features: string[] = []): Space => ({
  enabled_modules: MODULES.filter(key => !modules.includes(key)), enabled_features: FEATURES.filter(key => !features.includes(key)) });
const consoleFor = (role: string, space: Space = everything) => {
  const access = tabsFor(role);
  const tabs = filterTabsByEnabledModules(access.allowedTabs, space, ROLE_ACTIONS[role]);
  return { tabs, landing: staffLandingTab(tabs), nav: sidebarSections(tabs, "dashboard", undefined, undefined, access.handoutOnly, role === "space_manager") };
};
const headings = (nav: ShellSection[]) => nav.map(section => section.label ?? section.key);
const navKeys = (nav: ShellSection[]) => nav.flatMap(section => [...section.items, ...section.more ?? []].map(item => item.key));

describe("role-screen audit: sidebar per role, all modules on", () => {
  it.each([
    ["inventory_manager", ["home", "Front desk", "Inventory", "Money", "Insights", "Organizations", "Tools"]],
    ["machine_manager", ["home", "Front desk", "Machines", "Money", "Insights", "Organizations", "Tools"]],
    ["event_manager", ["home", "Events", "Money", "Insights", "Organizations", "Tools"]],
    ["booking_manager", ["home", "Bookings", "Money", "Insights", "Organizations", "Tools"]],
    ["technician", ["home", "Maintenance", "Insights", "Organizations", "Tools"]],
    ["shop_manager", ["home", "Shop", "Money", "Insights", "Organizations", "Tools"]],
    ["handover", ["desk"]],
    ["space_manager", ["Today", "People", "Inventory & loans", "Machines", "Events", "Bookings", "Shop", "Money", "Insights", "Space settings"]],
  ])("%s gets only its own areas as headings", (role, expected) => {
    expect(headings(consoleFor(role).nav)).toEqual(expected);
  });

  it("files the shared upkeep pages under the area the role runs", () => {
    const section = (role: string, key: string) => consoleFor(role).nav.find(row => row.key === key);
    // Item repairs and procurement belong to the inventory desk; room repairs to bookings.
    expect(section("inventory_manager", "inventory")?.items.map(item => item.key)).toEqual(expect.arrayContaining(["repairs", "tobuy", "consumables"]));
    expect(section("booking_manager", "bookings")?.items.map(item => item.key)).toEqual(["bookings", "repairs"]);
    expect(section("machine_manager", "machines")?.items.map(item => item.key)).toEqual(["machines", "repairs", "tobuy", "consumables", "warranty"]);
    expect(section("technician", "maintenance")?.items.map(item => item.key)).toEqual(["repairs"]);
  });

  it("keeps money out of the Front desk heading", () => {
    for (const role of ["inventory_manager", "machine_manager"]) {
      const desk = consoleFor(role).nav.find(section => section.key === "desk")!;
      expect(desk.items.map(item => item.key).filter(key => ["payments", "refunds", "finance"].includes(key)), role).toEqual([]);
    }
  });

  it("lays the handover desk out as its counter pages (four bottom tabs plus More on a phone)", () => {
    expect(navKeys(consoleFor("handover").nav)).toEqual(["dashboard", "requests", "direct", "handover", "payments", "notifications", "ledger"]);
  });
});

// The destinations of every OTHER area. Pinned per role so a widening shows up here.
const AREA_TABS: Record<string, string[]> = {
  inventory: ["inventory", "categories", "needsfix", "ledger", "stocktake", "transfers", "containers", "bulk", "qr", "scanner", "accountability", "requests", "direct"],
  machines: ["machines", "devices", "handover"],
  events: ["events"],
  bookings: ["bookings"],
  shop: ["shop"],
  people: ["members", "cards", "users"],
  space: ["settings", "security", "modules", "exports", "backups", "usage", "email-logs", "analytics", "payments"],
  donations: ["donations"],
};
const OWN_AREAS: Record<string, string[]> = {
  inventory_manager: ["inventory"], machine_manager: ["machines"], event_manager: ["events"], booking_manager: ["bookings"],
  technician: [], shop_manager: ["shop"], handover: [], fundraising: ["donations"],
};
// Decision 217 exceptions: the Event Manager settles event fees on Payments; the handover
// desk works requests, handouts and job pickups.
// Decision 242(a): every charge owner reads their own-area Payments queue. Audit IN11: the desk reads the Ledger.
const ALLOWED_ACROSS: Record<string, string[]> = { event_manager: ["payments"], inventory_manager: ["payments"],
  machine_manager: ["payments"], booking_manager: ["payments"], shop_manager: ["payments"],
  handover: ["requests", "direct", "handover", "ledger", "payments"] }; // decision 259: loan charges only

describe("role-screen audit: nothing outside the role's own area", () => {
  it.each(Object.keys(OWN_AREAS))("%s sees no other area's pages in tabs or sidebar", role => {
    const { tabs, nav } = consoleFor(role);
    const shown = navKeys(nav);
    for (const [area, areaTabs] of Object.entries(AREA_TABS)) {
      if (OWN_AREAS[role].includes(area)) continue;
      for (const tab of areaTabs.filter(key => !(ALLOWED_ACROSS[role] ?? []).includes(key))) {
        expect(tabs, `${role} tab ${tab}`).not.toContain(tab);
        expect(shown, `${role} sidebar ${tab}`).not.toContain(tab);
      }
    }
  });

  it("keeps the handover desk off reports, audit, incidents and money", () => {
    const { tabs } = consoleFor("handover");
    for (const tab of ["reports", "audit", "incidents", "refunds", "finance", "tobuy", "consumables", "repairs", "organizations"]) {
      expect(tabs).not.toContain(tab);
    }
  });

  it("gives a type-scoped Machine Manager the same tabs (the server narrows every row to their types)", () => {
    const scoped = getStaffAccess(ROLE_ACTIONS.machine_manager, false, false, true);
    expect(scoped.allowedTabs).toEqual(tabsFor("machine_manager").allowedTabs);
  });
});

describe("role-screen audit: module and capability switches", () => {
  it.each([
    ["event_manager", without(["events"]), ["events"], "dashboard"],
    ["booking_manager", without(["bookings"], ["bookings.room_repairs"]), ["bookings", "repairs"], "dashboard"],
    ["machine_manager", without(["machines", "machine_service"]), ["machines", "handover"], "dashboard"],
    ["shop_manager", without(["shop"]), ["shop"], "dashboard"],
    ["technician", without([], ["machines.repairs", "inventory.repairs", "bookings.room_repairs"]), ["repairs"], "dashboard"],
    ["inventory_manager", without([], ["loans.enabled"]), ["requests", "inventory", "direct", "ledger", "accountability", "stocktake"], "dashboard"],
    ["handover", without(["machine_service"], ["inventory.self_checkout"]), ["handover", "direct"], "dashboard"],
    ["space_manager", without(["reports", "analytics", "notifications"], ["safety.incidents"]), ["reports", "analytics", "notifications", "incidents"], "dashboard"],
  ] as [string, Space, string[], string][])("%s: switching the module off removes %j and keeps a sensible landing", (role, space, gone, landing) => {
    const { tabs, nav, landing: home } = consoleFor(role, space);
    for (const tab of gone) {
      expect(tabs, `${role} ${tab}`).not.toContain(tab);
      expect(navKeys(nav), `${role} ${tab}`).not.toContain(tab);
    }
    expect(home).toBe(landing);
  });

  it("opens Donations to the Space Manager and Fundraising only, and only while donations are on (decision 242 m)", () => {
    const on: Space = { ...everything, enabled_features: [...FEATURES, "finance.donations"] };
    expect(consoleFor("fundraising", on).tabs).toContain("donations");
    expect(consoleFor("fundraising", on).landing).toBe("donations");
    expect(consoleFor("space_manager", on).tabs).toContain("donations");
    for (const role of Object.keys(EXPECTED).filter(role => role !== "fundraising")) {
      expect(consoleFor(role, on).tabs, role).not.toContain("donations");
    }
    expect(consoleFor("fundraising").tabs).not.toContain("donations");
  });

  it("drops an area heading once its last page is switched off", () => {
    expect(headings(consoleFor("event_manager", without(["events"])).nav)).not.toContain("Events");
    expect(headings(consoleFor("shop_manager", without(["shop"])).nav)).not.toContain("Shop");
  });
});

describe("role-screen audit: people without a space role", () => {
  it("lands a superadmin without a chosen space on the platform dashboard", () => {
    const access = getStaffAccess([], true, false);
    expect(access.defaultTab).toBe("platform-dashboard");
    for (const tab of ["dashboard", "inventory", "events", "settings"]) expect(access.allowedTabs).not.toContain(tab);
    expect(getStaffAccess([], true, true).allowedTabs).not.toContain("platform-dashboard");
  });

  it("gives an event co-organizer (grant only) their assigned resources, and organizer pages only in an organization", () => {
    expect(getStaffAccess([], false, false, false, true).allowedTabs).toEqual(["granted", "organizations", "organized", "organization-analytics"]);
    expect(getStaffAccess([], false, false, false, true, false, false).allowedTabs).toEqual(["granted"]);
    expect(getStaffAccess([], false, true, false, true).allowedTabs).toEqual(["granted"]);
    expect(getStaffAccess([], false, false, false, true).defaultTab).toBe("granted");
  });

  it("opens organizer pages to an organization member with no space role (served by IsActiveStaff)", () => {
    const access = getStaffAccess([], false, false);
    expect(access.allowedTabs).toEqual(["organizations", "organized", "organization-analytics"]);
    expect(access.defaultTab).toBe("organizations");
  });

  it("hides the Organizations group from staff in no organization", () => {
    const tabs = getStaffAccess(ROLE_ACTIONS.event_manager, false, false, false, false, false, false).allowedTabs;
    for (const tab of ["organizations", "organized", "organization-analytics"]) expect(tabs).not.toContain(tab);
  });
});

// Decision 241 (owner: "they should see everything they manage too, like finance"): every
// area manager opens Finance (the server narrows rows to their area, a Machine Manager to their
// machine types) plus their area's upkeep lists, reports, audit log and inbox, which the grouped
// views link to. The Technician's money stays closed; payouts stay with finance staff.
describe("decision 241: each area manager's complete view", () => {
  const AREA_TABS: Record<string, string[]> = {
    inventory_manager: ["finance", "refunds", "tobuy", "consumables", "repairs", "warranty", "reports", "audit", "notifications"],
    machine_manager: ["finance", "refunds", "tobuy", "consumables", "repairs", "warranty", "reports", "audit", "notifications"],
    event_manager: ["finance", "refunds", "payments", "reports", "audit", "notifications"],
    booking_manager: ["finance", "refunds", "repairs", "reports", "audit", "notifications"],
    shop_manager: ["finance", "refunds", "reports", "audit", "notifications"],
    technician: ["repairs", "reports", "audit", "notifications"],
  };

  it.each(Object.entries(AREA_TABS))("%s reaches every view of its own area, all switches on", (role, tabs) => {
    expect(consoleFor(role).tabs).toEqual(expect.arrayContaining(tabs));
  });

  it("opens Finance to every area manager (machine-type narrowing is the server's) and never to the desk roles", () => {
    for (const role of ["inventory_manager", "machine_manager", "event_manager", "booking_manager", "shop_manager", "space_manager"]) {
      expect(consoleFor(role).tabs, role).toContain("finance");
      expect(consoleFor(role).nav.find(section => section.key === "money" || section.label === "Money")?.items
        .map(item => item.key), role).toContain("finance");
    }
    for (const role of ["technician", "handover"]) expect(consoleFor(role).tabs, role).not.toContain("finance");
    for (const actions of [["manage_machines"], ["manage_events"], ["manage_bookings"], ["edit_inventory"], ["manage_shop"]]) {
      expect(getStaffAccess(actions, false, false).allowedTabs, actions[0]).toContain("finance");
    }
  });

  it("drops Finance for an area manager once every finance switch is off", () => {
    const off = without([], ["finance.ledger"]);
    for (const role of ["inventory_manager", "machine_manager", "event_manager", "booking_manager", "shop_manager"]) {
      expect(consoleFor(role, off).tabs, role).not.toContain("finance");
    }
  });

  it("opens Payments as the own-area queue to every charge owner, never to the Technician (decision 242 a)", () => {
    for (const role of ["inventory_manager", "machine_manager", "booking_manager", "shop_manager", "event_manager"]) {
      expect(consoleFor(role).tabs, role).toContain("payments");
    }
    expect(consoleFor("technician").tabs).not.toContain("payments");
  });
});

// Decision 242(k)/(l): the Schedule follows the server's layer rules, and the cross-space inbox is the superadmin's alone.
describe("decision 242: Schedule and the platform inbox", () => {
  it("opens the Schedule to every role that runs a layer, never to the counter desk or the shop", () => {
    for (const role of ["space_manager", "inventory_manager", "machine_manager", "event_manager", "booking_manager", "technician"]) {
      expect(tabsFor(role).allowedTabs, role).toContain("schedule");
    }
    for (const role of ["handover", "shop_manager"]) expect(tabsFor(role).allowedTabs, role).not.toContain("schedule");
    expect(consoleFor("space_manager").nav.find(section => section.key === "today")?.items.map(item => item.key)).toContain("schedule");
  });

  it("keeps the cross-space inbox on the platform console only", () => {
    expect(getStaffAccess([], true, false).allowedTabs).toContain("platform-inbox");
    expect(getStaffAccess([], true, true).allowedTabs).not.toContain("platform-inbox");
    for (const role of Object.keys(ROLE_ACTIONS)) expect(tabsFor(role).allowedTabs, role).not.toContain("platform-inbox");
  });
});

// Decision 242 (lane C2): area money and role consoles. Payments opens for whoever owns a charge
// type (reconciliation_authority.SUBJECT_ACTIONS); the handout desk stays narrow (217(b)).
describe("decision 242: own-area Payments queue and the Shop/Technician dashboards", () => {
  it.each([["manage_machines"], ["manage_bookings"], ["manage_events"], ["manage_shop"], ["edit_inventory", "return_request"],
    ["manage_members"]])("opens Payments to a charge owner holding %s", (...actions) => {
    expect(getStaffAccess(actions, false, false).allowedTabs).toContain("payments");
  });

  it("keeps Payments shut for actors who own no area charge", () => {
    for (const actions of [["work_repairs"], ["manage_donations"], ["view_audit"], ["edit_inventory"]]) {
      expect(getStaffAccess(actions, false, false).allowedTabs, actions[0]).not.toContain("payments");
    }
  });

  it("opens Payments to the handout desk for loan charges (no record_payment needed, decision 259)", () => {
    expect(getStaffAccess(ROLE_ACTIONS.handover, false, false).allowedTabs).toContain("payments");
    expect(getStaffAccess(["issue_request"], false, false).allowedTabs).toContain("payments");
    expect(getStaffAccess(["collect_service_request", "view_inventory"], false, false).allowedTabs).not.toContain("payments");
    expect(getStaffAccess([...ROLE_ACTIONS.handover, "record_payment"], false, false).allowedTabs).toContain("payments");
  });

  it("serves the Shop Manager and the Technician a dashboard and lands them on it", () => {
    for (const role of ["shop_manager", "technician"]) {
      const { tabs, landing } = consoleFor(role);
      expect(tabs, role).toContain("dashboard");
      expect(landing, role).toBe("dashboard");
    }
    expect(getStaffAccess(["manage_donations"], false, false).allowedTabs).not.toContain("dashboard");
  });

  it("files Payments under the Money heading for an area manager", () => {
    for (const role of ["machine_manager", "booking_manager", "shop_manager"]) {
      const money = consoleFor(role).nav.find(section => section.key === "money");
      expect(money?.items.map(item => item.key), role).toContain("payments");
    }
  });
});

// Parity O-B1/O-F1: the member-unit actions. The Space Manager holds both by default; a unit lead
// (members work narrowed to one unit) reads the tree. Neither action opens a tab of its own: the
// tree lives in Members › Units and Settings › People, so the per-role consoles above are unchanged.
describe("member units (parity O-F1)", () => {
  it("gives the Space Manager and the superadmin the unit editor", () => {
    expect(tabsFor("space_manager").canManageMemberUnits).toBe(true);
    expect(tabsFor("space_manager").canViewMemberUnits).toBe(true);
    expect(getStaffAccess(["manage_makerspace"], true, false).canManageMemberUnits).toBe(true);
  });

  it("lets a view-only unit lead read the tree but not edit it", () => {
    const lead = getStaffAccess(["manage_members", "view_member_units"], false, false);
    expect(lead.canViewMemberUnits).toBe(true);
    expect(lead.canManageMemberUnits).toBe(false);
    expect(lead.allowedTabs).toContain("members");
  });

  it("never grants the unit editor to an area role, and the unit actions open no extra tab", () => {
    for (const role of Object.keys(EXPECTED)) {
      expect(tabsFor(role).canManageMemberUnits, role).toBe(false);
      expect(tabsFor(role).canViewMemberUnits, role).toBe(false);
    }
    const withUnits = getStaffAccess(["manage_member_units", "view_member_units"], false, false).allowedTabs;
    expect([...withUnits].sort()).toEqual([...getStaffAccess(["view_member_units"], false, false).allowedTabs].sort());
    expect(withUnits).not.toContain("members");
    expect(withUnits).not.toContain("settings");
  });
});
