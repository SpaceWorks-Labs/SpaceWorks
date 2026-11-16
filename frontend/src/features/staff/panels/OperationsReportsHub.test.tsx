import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, within } from "@testing-library/react";
import { OperationsReports } from "./OperationsReports";
import { mockAnalyticsFetch, renderAnalytics, reportData, reportItem, space } from "../../../test/analyticsFixtures";

afterEach(() => { vi.unstubAllGlobals(); window.localStorage.clear(); window.history.replaceState({}, "", "/"); });
beforeEach(() => window.localStorage.clear());

const entry = (key: string, group: string, label: string, order: number, title: string) =>
  reportItem(key, { title, group, group_label: label, group_order: order });
const catalog = { results: [
  entry("machine-usage", "machines", "Machines", 2, "Machine usage"),
  entry("machine-access-grants", "machines", "Machines", 2, "Machine access grants"),
  entry("event-certificates-issued", "events", "Events", 3, "Event certificates issued"),
  entry("device-adapter-activity", "devices", "Connected devices", 10, "Device adapter activity"),
] };
const mount = (modules = space.enabled_modules) => {
  mockAnalyticsFetch(url => url.pathname.endsWith("catalog") ? catalog : reportData());
  return renderAnalytics(<OperationsReports makerspace={{ ...space, enabled_modules: modules }} makerspaces={[space]}
    isSuperadmin={false} canViewAudit={false} canManageMachines />);
};

describe("Reports hub", () => {
  it("groups reports by module and offers a chip per group", async () => {
    mount();
    expect(await screen.findByRole("region", { name: "Machines" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Events" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Connected devices" })).toBeInTheDocument();
    const chips = screen.getByRole("group", { name: "Module" });
    expect(within(chips).getByRole("button", { name: "Machines (2)" })).toBeInTheDocument();
  });

  it("searches reports by name", async () => {
    mount();
    await screen.findByRole("region", { name: "Machines" });
    fireEvent.change(screen.getByLabelText("Search reports"), { target: { value: "certificates" } });
    expect(screen.queryByRole("region", { name: "Machines" })).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Events" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Search reports"), { target: { value: "zzz" } });
    expect(await screen.findByText(/No report matches this search/)).toBeInTheDocument();
  });

  it("opens straight onto the module group named in the link", async () => {
    window.history.replaceState({}, "", "/?group=events");
    mount();
    expect(await screen.findByRole("region", { name: "Events" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Machines" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Events (1)" })).toHaveAttribute("aria-pressed", "true");
  });

  it("pins a report to the top and remembers it", async () => {
    const view = mount();
    await screen.findByRole("region", { name: "Events" });
    const events = screen.getByRole("region", { name: "Events" });
    fireEvent.click(within(events).getByRole("button", { name: "Pin Event certificates issued" }));
    const pinned = await screen.findByRole("region", { name: "Pinned" });
    expect(within(pinned).getByText("Event certificates issued")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Events" })).not.toBeInTheDocument();
    view.unmount();
    mount();
    expect(await screen.findByRole("region", { name: "Pinned" })).toBeInTheDocument();
  });

  it("says why nothing is listed when the Reports module is off", async () => {
    mount(["machines"]);
    expect(await screen.findByText(/Reports are switched off for this makerspace/)).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Machines" })).not.toBeInTheDocument();
  });

  it("says why nothing is listed when the role unlocks no report", async () => {
    mockAnalyticsFetch(url => url.pathname.endsWith("catalog") ? { results: [] } : reportData());
    renderAnalytics(<OperationsReports makerspace={space} makerspaces={[space]} isSuperadmin={false} canViewAudit={false} canManageMachines={false} />);
    expect(await screen.findByText(/No report is available to your role here/)).toBeInTheDocument();
  });

  it("hides a report the catalog marks unavailable", async () => {
    mockAnalyticsFetch(url => url.pathname.endsWith("catalog")
      ? { results: [...catalog.results, { ...entry("booking-occupancy", "bookings", "Bookings", 4, "Booking occupancy"), available: false }] } : reportData());
    renderAnalytics(<OperationsReports makerspace={space} makerspaces={[space]} isSuperadmin={false} canViewAudit={false} canManageMachines />);
    await screen.findByRole("region", { name: "Machines" });
    expect(screen.queryByRole("region", { name: "Bookings" })).not.toBeInTheDocument();
  });
});
