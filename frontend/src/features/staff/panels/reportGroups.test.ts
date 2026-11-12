import { describe, expect, it } from "vitest";
import { filterReports, groupChoices, groupReports, hubEmptyReason, matchesQuery, reportGroupOf } from "./reportGroups";
import { reportItem } from "../../../test/analyticsFixtures";

const grouped = (key: string, group: string, label: string, order: number, title = key.replace(/-/g, " ")) =>
  reportItem(key, { title, group, group_label: label, group_order: order });
const catalog = [
  grouped("machine-usage", "machines", "Machines", 2),
  grouped("machine-access-grants", "machines", "Machines", 2, "Machine access grants"),
  grouped("event-certificates-issued", "events", "Events", 3, "Event certificates issued"),
  grouped("device-adapter-activity", "devices", "Connected devices", 10, "Device adapter activity"),
  grouped("platform-usage", "platform", "Platform", 12),
];

describe("report hub grouping", () => {
  it("groups by the server module group in the module-switch order", () => {
    expect(groupReports(catalog).map(group => [group.label, group.reports.length])).toEqual([
      ["Machines", 2], ["Events", 1], ["Connected devices", 1], ["Platform", 1]]);
  });

  it("falls back to the legacy area when the catalog carries no group", () => {
    expect(reportGroupOf(reportItem("machine-usage")).label).toBe("Machines & service");
    expect(groupReports([reportItem("booking-occupancy"), reportItem("machine-usage")]).map(group => group.label)).toEqual(["Machines & service", "Bookings"]);
  });

  it("searches title, key and group name", () => {
    expect(filterReports(catalog, "certificates", "").map(report => report.key)).toEqual(["event-certificates-issued"]);
    expect(filterReports(catalog, "connected", "").map(report => report.key)).toEqual(["device-adapter-activity"]);
    expect(matchesQuery(catalog[0], "  ")).toBe(true);
    expect(filterReports(catalog, "nothing like this", "")).toEqual([]);
  });

  it("filters to one module group, as the Reports link inside a module area asks", () => {
    expect(filterReports(catalog, "", "machines").map(report => report.key)).toEqual(["machine-usage", "machine-access-grants"]);
    expect(groupChoices(catalog).map(choice => [choice.key, choice.count])).toEqual([["machines", 2], ["events", 1], ["devices", 1], ["platform", 1]]);
  });

  it("lifts pinned reports into a leading group without duplicating them", () => {
    const groups = groupReports(catalog, new Set(["event-certificates-issued"]), "Pinned");
    expect(groups.map(group => group.label)).toEqual(["Pinned", "Machines", "Connected devices", "Platform"]);
    expect(groups[0].reports.map(report => report.key)).toEqual(["event-certificates-issued"]);
  });

  it("says why the hub is empty", () => {
    expect(hubEmptyReason({ reportsEnabled: false, catalogCount: 0, visibleCount: 0 })).toBe("module_off");
    expect(hubEmptyReason({ reportsEnabled: true, catalogCount: 0, visibleCount: 0 })).toBe("no_access");
    expect(hubEmptyReason({ reportsEnabled: true, catalogCount: 5, visibleCount: 0 })).toBe("no_match");
    expect(hubEmptyReason({ reportsEnabled: true, catalogCount: 5, visibleCount: 2 })).toBeNull();
  });
});
