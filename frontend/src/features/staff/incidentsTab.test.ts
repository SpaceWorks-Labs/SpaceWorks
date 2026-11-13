import { describe, expect, it } from "vitest";

import { sidebarSections } from "./sidebarSections";
import { getStaffAccess } from "./staffAccess";
import { filterTabsByEnabledModules } from "./staffTabs";

const tabs = (actions: string[]) => getStaffAccess(actions, false, false).allowedTabs;
const space = (features: string[]) => ({ enabled_modules: ["machines", "events", "bookings"], enabled_features: features });

describe("decision 223 (k): the Incidents staff tab", () => {
  it("opens to the Space Manager and every area reader, never to the desk or shop roles", () => {
    for (const actions of [["manage_makerspace"], ["manage_machines"], ["manage_printing"], ["edit_inventory"], ["accept_request"],
      ["manage_events"], ["manage_bookings"]]) expect(tabs(actions), actions.join()).toContain("incidents");
    for (const actions of [["work_repairs"], ["manage_shop", "sell_shop"], ["view_finance"], ["manage_members"],
      ["issue_request", "return_request", "upload_evidence"]]) expect(tabs(actions), actions.join()).not.toContain("incidents");
  });

  it("is shown only while safety.incidents is on, and sits in the sidebar", () => {
    const allowed = tabs(["manage_events"]);
    expect(filterTabsByEnabledModules(allowed, space([]))).not.toContain("incidents");
    const on = filterTabsByEnabledModules(allowed, space(["safety.incidents"]));
    expect(on).toContain("incidents");
    const keys = sidebarSections(on, "incidents").flatMap(section => section.items.map(item => item.key));
    expect(keys).toContain("incidents");
    const manager = sidebarSections(filterTabsByEnabledModules(tabs(["manage_makerspace"]), space(["safety.incidents"])), "dashboard",
      undefined, undefined, false, true);
    expect(manager.find(section => section.key === "today")?.items.map(item => item.key)).toContain("incidents");
  });
});
