import { describe, expect, it } from "vitest";
import type { TenantBootstrap } from "../../lib/api";
import { publicFamilies } from "../../lib/publicHome";
import { memberTabs } from "../members/MemberPortalTabs";
import { filterTabsByEnabledModules } from "./staffTabs";
import { getStaffAccess, staffLandingTab } from "./staffAccess";
import { spaceManagerActions } from "../../test/staffActor";

// Decision 254: every on/off pattern of the six areas must give a coherent staff console, public site and member area.
const AREAS = ["inventory", "machines", "events", "bookings", "shop", "membership"] as const;
type Area = typeof AREAS[number];
const CORE = ["staff_admin", "notifications", "member_accounts", "public_inventory", "request_workflow", "qr_management", "evidence_uploads", "scanner"];
const AREA_MODULES: Record<Area, string[]> = {
  inventory: ["containers", "stocktake", "bulk_import", "qr_print_batches", "stock_transfers", "guest_handover"],
  machines: ["machines", "machine_service", "printing"], events: ["events"], bookings: ["bookings"], shop: ["shop"], membership: ["membership"],
};
const AREA_FEATURES: Record<Area, string[]> = {
  inventory: ["loans.enabled", "inventory.self_checkout", "inventory.tobuy", "inventory.warranty", "loans.renewals"],
  machines: ["machines.tobuy", "machines.warranty"], events: [], bookings: [], shop: [], membership: [],
};
const INVENTORY_TABS = ["requests", "inventory", "categories", "needsfix", "ledger", "accountability", "direct", "containers", "transfers", "stocktake", "bulk", "qr", "scanner"];
const allTabs = getStaffAccess(spaceManagerActions, false, false).allowedTabs;

const combos = Array.from({ length: 1 << AREAS.length }, (_, mask) => AREAS.filter((_, bit) => mask & (1 << bit)));
const label = (on: readonly Area[]) => on.length ? on.join("+") : "none";

describe.each(combos)("areas on: %s", (...on) => {
  const has = (area: Area) => on.includes(area);
  const modules = [...CORE, ...on.flatMap(area => AREA_MODULES[area])];
  const features = on.flatMap(area => AREA_FEATURES[area]);
  const tabs = filterTabsByEnabledModules(allTabs, { enabled_modules: modules, enabled_features: features });

  it(`${label(on)}: staff nav has no tab of an off area and a real landing page`, () => {
    for (const tab of INVENTORY_TABS) expect(tabs.includes(tab), tab).toBe(has("inventory") && allTabs.includes(tab));
    expect(tabs.includes("machines")).toBe(has("machines"));
    expect(tabs.includes("events")).toBe(has("events"));
    expect(tabs.includes("bookings")).toBe(has("bookings"));
    expect(tabs.includes("shop")).toBe(has("shop"));
    expect(tabs.includes("tobuy")).toBe(has("inventory") || has("machines"));
    expect(tabs.includes("warranty")).toBe(has("inventory") || has("machines"));
    for (const tab of ["dashboard", "settings", "users", "audit", "members", "modules"]) expect(tabs).toContain(tab);
    expect(staffLandingTab(tabs)).toBe("dashboard");
  });

  it(`${label(on)}: public site lists exactly the areas that are on, in a fixed order`, () => {
    const bootstrap = { makerspace: { public_site_enabled: true, public_inventory_enabled: true }, modules, features } as unknown as TenantBootstrap;
    const families = publicFamilies(bootstrap);
    expect(families.includes("inventory")).toBe(has("inventory"));
    for (const family of ["events", "bookings", "machines", "membership"] as const) expect(families.includes(family)).toBe(has(family));
    expect(new Set(families).size).toBe(families.length);
  });

  it(`${label(on)}: member area offers a tab only for an area that is on`, () => {
    const member = memberTabs(modules, features);
    expect(member).toContain("overview");
    expect(member.includes("loans")).toBe(has("inventory") && has("membership"));
    expect(member.includes("events")).toBe(has("events") && has("membership"));
    expect(member.includes("bookings")).toBe(has("bookings"));
  });
});
